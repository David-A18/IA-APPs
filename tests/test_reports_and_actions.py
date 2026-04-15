"""Tests for report generators, alert sender, PR generator, savings tracker."""

from pathlib import Path
import json
import pytest


# ── JSON reporter ─────────────────────────────────────────────────────────────

def test_json_report_structure(in_memory_store):
    from finops.reports.json_reporter import generate_json_report
    from finops.analysis.anomaly_detector import detect_anomalies

    anomalies = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    report = generate_json_report(
        account_id="123456789012",
        start_date="2024-01-15",
        end_date="2024-01-18",
        total_cost=50.0,
        anomalies=anomalies,
    )
    assert "meta" in report
    assert "summary" in report
    assert "anomalies" in report
    assert "recommendations" in report
    assert report["meta"]["account_id"] == "123456789012"
    assert report["summary"]["total_cost_usd"] == 50.0


def test_json_report_write_file(tmp_path, in_memory_store):
    from finops.reports.json_reporter import generate_json_report, write_json_report
    from finops.analysis.anomaly_detector import detect_anomalies

    anomalies = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    report = generate_json_report("123456789012", "2024-01-15", "2024-01-18", 50.0, anomalies)
    output = tmp_path / "reports" / "report.json"
    write_json_report(report, output)

    assert output.exists()
    loaded = json.loads(output.read_text())
    assert loaded["meta"]["account_id"] == "123456789012"


def test_json_report_savings_sum():
    from finops.reports.json_reporter import generate_json_report

    class FakeEC2:
        estimated_savings_usd = 30.0
        def as_dict(self): return {"savings": 30.0}

    class FakeStorage:
        estimated_savings_usd = 10.0
        def as_dict(self): return {"savings": 10.0}

    report = generate_json_report(
        "123456789012", "2024-01-01", "2024-01-31", 200.0, [],
        ec2_recommendations=[FakeEC2()],
        storage_recommendations=[FakeStorage()],
    )
    assert report["summary"]["estimated_monthly_savings_usd"] == 40.0


# ── Markdown reporter ─────────────────────────────────────────────────────────

def test_markdown_report_renders(in_memory_store):
    from finops.reports.markdown_reporter import generate_markdown_report
    from finops.analysis.anomaly_detector import detect_anomalies

    anomalies = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    md = generate_markdown_report(
        account_id="123456789012",
        start_date="2024-01-15",
        end_date="2024-01-18",
        total_cost=50.0,
        anomalies=anomalies,
    )
    assert "# FinOps Autopilot Report" in md
    assert "123456789012" in md
    assert "2024-01-15" in md


def test_markdown_report_contains_summary():
    from finops.reports.markdown_reporter import generate_markdown_report

    md = generate_markdown_report("acct", "2024-01-01", "2024-01-31", 150.0, [])
    assert "Summary" in md
    assert "$150.00" in md
    assert "No anomalies detected" in md


def test_pr_body_renders():
    from finops.reports.markdown_reporter import generate_pr_body

    body = generate_pr_body(
        changes=[{
            "resource_id": "i-abc",
            "action": "downsize",
            "current_value": "t3.large",
            "recommended_value": "t3.medium",
            "savings_usd": 20.0,
            "confidence": "high",
        }],
        estimated_savings=20.0,
        evaluation_period_days=14,
        metrics_source="CloudWatch",
        rules_applied=["ec2_low_cpu"],
    )
    assert "FinOps Autopilot" in body
    assert "i-abc" in body
    assert "$20.00" in body
    assert "Human approval required" in body


def test_markdown_write_file(tmp_path):
    from finops.reports.markdown_reporter import write_markdown_report

    output = tmp_path / "out" / "report.md"
    write_markdown_report("# Test Report\n\ncontent here", output)
    assert output.exists()
    assert "Test Report" in output.read_text()


# ── Alert sender ──────────────────────────────────────────────────────────────

def test_slack_alert_dry_run(capsys, in_memory_store):
    from finops.actions.alert_sender import send_slack_alert
    from finops.analysis.anomaly_detector import detect_anomalies

    anomalies = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    result = send_slack_alert(
        webhook_url="https://hooks.slack.com/services/PLACEHOLDER",
        anomalies=anomalies[:2],
        account_id="123456789012",
        period="2024-01-18",
        dry_run=True,
    )
    assert result is True
    captured = capsys.readouterr()
    if anomalies:
        assert "blocks" in captured.out


def test_slack_alert_empty_anomalies():
    from finops.actions.alert_sender import send_slack_alert
    result = send_slack_alert("https://example.com", [], "acct", "period")
    assert result is True


def test_json_alert_writes_file(tmp_path, in_memory_store):
    from finops.actions.alert_sender import send_json_alert
    from finops.analysis.anomaly_detector import detect_anomalies

    anomalies = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    output = tmp_path / "alerts.json"
    send_json_alert(anomalies, output, "123456789012", "2024-01-18")

    assert output.exists()
    data = json.loads(output.read_text())
    assert data["account_id"] == "123456789012"
    assert "anomalies" in data


def test_dispatch_alerts_json_enabled(tmp_path, in_memory_store):
    from finops.actions.alert_sender import dispatch_alerts
    from finops.analysis.anomaly_detector import detect_anomalies

    anomalies = detect_anomalies(in_memory_store, end_date="2024-01-18", lookback_days=3)
    config = {
        "alerts": {
            "slack": {"enabled": False, "webhook_url": "", "channel": "#ch"},
            "json_output": {"enabled": True, "output_path": str(tmp_path / "alerts.json")},
        }
    }
    results = dispatch_alerts(anomalies, config, "acct", "2024-01-18")
    assert results.get("json") is True


# ── PR generator ──────────────────────────────────────────────────────────────

def test_build_terraform_changes_ec2_downsize():
    from finops.actions.pr_generator import build_terraform_changes
    from finops.recommendations.ec2_rightsizer import EC2Recommendation

    rec = EC2Recommendation(
        rule_id="ec2_low_cpu", rule_name="EC2 low CPU", instance_id="i-abc",
        instance_type="t3.large", region="us-east-1", action="recommend_downsize",
        recommended_type="t3.medium", cpu_avg_pct=8.0, memory_avg_pct=20.0,
        monthly_cost_usd=50.0, estimated_savings_usd=15.0,
        confidence="high", reason="CPU < 20%",
    )
    changes = build_terraform_changes([rec], [])
    assert len(changes) == 1
    assert changes[0]["action"] == "downsize"
    assert "t3.medium" in changes[0]["terraform_snippet"]


def test_generate_pr_dry_run():
    from finops.actions.pr_generator import generate_pr
    from finops.recommendations.ec2_rightsizer import EC2Recommendation

    rec = EC2Recommendation(
        rule_id="ec2_low_cpu", rule_name="Low CPU", instance_id="i-abc",
        instance_type="t3.large", region="us-east-1", action="recommend_downsize",
        recommended_type="t3.medium", cpu_avg_pct=8.0, memory_avg_pct=20.0,
        monthly_cost_usd=50.0, estimated_savings_usd=15.0,
        confidence="high", reason="low",
    )
    result = generate_pr([rec], [], evaluation_period_days=14,
                         metrics_source="CloudWatch", dry_run=True)
    assert result["status"] == "dry_run"
    assert "title" in result
    assert "$15" in result["title"]
    assert "body" in result


def test_generate_pr_no_changes():
    from finops.actions.pr_generator import generate_pr
    result = generate_pr([], [], evaluation_period_days=14, metrics_source="CloudWatch")
    assert result["status"] == "no_changes"


# ── Savings tracker ───────────────────────────────────────────────────────────

def test_record_and_verify_savings():
    from finops.actions.savings_tracker import (
        load_tracker, record_recommendation, mark_applied,
        verify_savings, get_accuracy_report,
    )

    tracker = load_tracker(Path("nonexistent.json"))
    record_recommendation(tracker, "rec-001", "i-abc", "downsize", 25.0, pr_url="https://pr/1")
    assert tracker["summary"]["total_estimated_usd"] == 25.0

    mark_applied(tracker, "rec-001")
    entry = tracker["entries"][0]
    assert entry["status"] == "applied"

    verify_savings(tracker, "rec-001", 22.0)
    entry = tracker["entries"][0]
    assert entry["status"] == "verified"
    assert tracker["summary"]["total_verified_usd"] == 22.0

    report = get_accuracy_report(tracker)
    assert report["verified_count"] == 1
    assert report["accuracy_pct"] == pytest.approx(88.0, abs=1)


def test_savings_tracker_persistence(tmp_path):
    from finops.actions.savings_tracker import load_tracker, record_recommendation, save_tracker

    tracker = load_tracker(Path("nonexistent.json"))
    record_recommendation(tracker, "rec-002", "vol-xyz", "migrate_to_gp3", 5.0)
    path = tmp_path / "tracker.json"
    save_tracker(tracker, path)

    loaded = load_tracker(path)
    assert len(loaded["entries"]) == 1
    assert loaded["entries"][0]["id"] == "rec-002"
