"""Tests for anomaly detector, top movers, and unit economics."""

from pathlib import Path

import pytest
import yaml

from finops.analysis.anomaly_detector import detect_anomalies, load_rules, AnomalyEvent
from finops.analysis.top_movers import compute_top_movers
from finops.analysis.unit_economics import compute_unit_economics


# ── Rules YAML ────────────────────────────────────────────────────────────────

def test_anomaly_rules_yaml_exists():
    rules_path = Path(__file__).parent.parent / "finops" / "config" / "rules" / "anomaly_rules.yaml"
    assert rules_path.exists()
    data = yaml.safe_load(rules_path.read_text())
    assert "rules" in data
    assert len(data["rules"]) > 0


def test_anomaly_rules_have_required_fields():
    rules_path = Path(__file__).parent.parent / "finops" / "config" / "rules" / "anomaly_rules.yaml"
    data = yaml.safe_load(rules_path.read_text())
    for rule in data["rules"]:
        assert "id" in rule
        assert "name" in rule
        assert "severity" in rule
        assert rule["severity"] in ("low", "medium", "high")


def test_load_rules_returns_enabled_only():
    rules = load_rules()
    assert all(r.get("enabled", True) for r in rules)


# ── Config validation ─────────────────────────────────────────────────────────

def test_config_validation_passes(sample_config, config_schema):
    from finops.utils.validators import validate_config
    validate_config(sample_config, config_schema)  # must not raise


def test_config_validation_fails_bad_account_id(config_schema):
    from finops.utils.validators import validate_config, ConfigValidationError

    bad_config = {
        "aws": {
            "account_id": "not-a-number",
            "region": "us-east-1",
            "cur": {"s3_bucket": "bucket", "s3_prefix": "prefix/", "report_name": "report"},
        },
        "anomaly_detection": {
            "thresholds": {
                "daily_cost_spike_pct": 20,
                "service_cost_spike_pct": 50,
                "absolute_min_delta_usd": 10.0,
            },
            "lookback_days": 7,
        },
        "rightsizing": {
            "ec2": {"cpu_threshold_pct": 20, "memory_threshold_pct": 30, "evaluation_period_days": 14},
            "storage": {"ebs_utilization_threshold_pct": 40},
        },
        "alerts": {
            "slack": {"enabled": False, "webhook_url": "https://example.com", "channel": "#ch"},
            "email": {"enabled": False, "recipients": []},
            "json_output": {"enabled": True, "output_path": "out.json"},
        },
        "reports": {"output_dir": "output/", "formats": ["json"]},
    }
    with pytest.raises(ConfigValidationError):
        validate_config(bad_config, config_schema)


# ── Anomaly detector ─────────────────────────────────────────────────────────

def test_detect_anomalies_returns_list(in_memory_store):
    events = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    assert isinstance(events, list)


def test_anomaly_events_have_required_fields(in_memory_store):
    events = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    for event in events:
        assert isinstance(event, AnomalyEvent)
        assert event.rule_id
        assert event.severity in ("low", "medium", "high")
        assert event.detected_date == "2024-01-18"
        assert event.delta_usd >= 0 or event.delta_pct is None  # new services have no pct


def test_detect_anomalies_empty_store():
    from finops.ingestion.local_store import LocalStore
    store = LocalStore()
    events = detect_anomalies(store, end_date="2024-01-18")
    assert events == []


def test_anomaly_event_as_dict(in_memory_store):
    events = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    if events:
        d = events[0].as_dict()
        assert "rule_id" in d
        assert "delta_usd" in d
        assert "severity" in d


# ── Top movers ───────────────────────────────────────────────────────────────

def test_top_movers_returns_dict(in_memory_store):
    result = compute_top_movers(
        in_memory_store,
        current_start="2024-01-18",
        current_end="2024-01-18",
        previous_start="2024-01-15",
        previous_end="2024-01-17",
    )
    assert "by_absolute" in result
    assert "by_percentage" in result
    assert "period" in result


def test_top_movers_by_absolute_sorted(in_memory_store):
    result = compute_top_movers(
        in_memory_store,
        current_start="2024-01-18",
        current_end="2024-01-18",
        previous_start="2024-01-15",
        previous_end="2024-01-17",
    )
    deltas = [m["delta_usd"] for m in result["by_absolute"]]
    assert deltas == sorted(deltas, reverse=True)


def test_top_movers_auto_previous_period(in_memory_store):
    result = compute_top_movers(
        in_memory_store,
        current_start="2024-01-18",
        current_end="2024-01-18",
    )
    assert result["period"]["previous"]["start"] < "2024-01-18"


# ── Unit economics ───────────────────────────────────────────────────────────

def test_unit_economics_returns_report(in_memory_store):
    report = compute_unit_economics(in_memory_store, "2024-01-15", "2024-01-18")
    assert report.total_cost > 0
    assert len(report.by_team) > 0
    assert len(report.by_category) > 0


def test_unit_economics_pct_sums_to_100(in_memory_store):
    report = compute_unit_economics(in_memory_store, "2024-01-15", "2024-01-18")
    total_pct = sum(r["pct_of_total"] for r in report.by_team)
    assert abs(total_pct - 100.0) < 1.0  # within 1% due to rounding


def test_unit_economics_as_dict(in_memory_store):
    report = compute_unit_economics(in_memory_store, "2024-01-15", "2024-01-18")
    d = report.as_dict()
    assert "period" in d
    assert "total_cost_usd" in d
    assert "by_team" in d
    assert "top_services" in d


def test_unit_economics_top_services_sorted(in_memory_store):
    report = compute_unit_economics(in_memory_store, "2024-01-15", "2024-01-18")
    costs = [r["total_cost"] for r in report.top_services]
    assert costs == sorted(costs, reverse=True)
