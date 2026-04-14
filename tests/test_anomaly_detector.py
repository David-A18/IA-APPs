"""Placeholder tests for anomaly detector (Week 3)."""

import pytest


# TODO: implement when finops/analysis/anomaly_detector.py is built (Week 3)


def test_anomaly_rules_yaml_exists():
    """Smoke test: anomaly_rules.yaml must be present and parseable."""
    from pathlib import Path
    import yaml

    rules_path = Path(__file__).parent.parent / "finops" / "config" / "rules" / "anomaly_rules.yaml"
    assert rules_path.exists(), "anomaly_rules.yaml not found"
    data = yaml.safe_load(rules_path.read_text())
    assert "rules" in data
    assert len(data["rules"]) > 0


def test_anomaly_rules_have_required_fields():
    """Each rule must have id, name, threshold fields."""
    from pathlib import Path
    import yaml

    rules_path = Path(__file__).parent.parent / "finops" / "config" / "rules" / "anomaly_rules.yaml"
    data = yaml.safe_load(rules_path.read_text())
    for rule in data["rules"]:
        assert "id" in rule, f"Rule missing 'id': {rule}"
        assert "name" in rule, f"Rule missing 'name': {rule}"
        assert "severity" in rule, f"Rule missing 'severity': {rule}"


def test_config_validation_passes(sample_config, config_schema):
    """Settings.yaml must pass JSON Schema validation."""
    from finops.utils.validators import validate_config

    validate_config(sample_config, config_schema)  # should not raise


def test_config_validation_fails_bad_account_id(config_schema):
    """Invalid account_id format must fail validation."""
    from finops.utils.validators import validate_config, ConfigValidationError
    import pytest

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
