"""Send alerts via Slack webhook, email, or JSON file."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def send_slack_alert(
    webhook_url: str,
    anomalies: list[Any],
    account_id: str,
    period: str,
    dry_run: bool = False,
) -> bool:
    """
    Send anomaly alert to Slack via webhook.

    Returns True if sent successfully, False otherwise.
    dry_run=True prints the payload without sending.
    """
    if not anomalies:
        return True

    high = [a for a in anomalies if a.severity == "high"]
    medium = [a for a in anomalies if a.severity == "medium"]
    low = [a for a in anomalies if a.severity == "low"]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🚨 FinOps Autopilot — {len(anomalies)} Anomalies Detected"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Account:* {account_id}"},
                {"type": "mrkdwn", "text": f"*Period:* {period}"},
                {"type": "mrkdwn", "text": f"*High:* {len(high)} | *Medium:* {len(medium)} | *Low:* {len(low)}"},
                {"type": "mrkdwn", "text": f"*Total delta:* ${sum(a.delta_usd for a in anomalies):+.2f}"},
            ],
        },
        {"type": "divider"},
    ]

    for anomaly in anomalies[:5]:  # Limit to 5 to avoid Slack message size limits
        subject = anomaly.service or anomaly.region or "total"
        pct = f"+{anomaly.delta_pct:.1f}%" if anomaly.delta_pct else "new"
        emoji = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(anomaly.severity, "⚪")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *{anomaly.rule_name}*\n"
                    f"  Service: `{subject}` | Delta: `${anomaly.delta_usd:+.2f}` ({pct})\n"
                    f"  Date: {anomaly.detected_date}"
                ),
            },
        })

    if len(anomalies) > 5:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_...and {len(anomalies) - 5} more anomalies._"},
        })

    payload = {"blocks": blocks}

    if dry_run:
        print(json.dumps(payload, indent=2))
        return True

    import requests

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"[alert_sender] Slack webhook failed: {e}")
        return False


def send_json_alert(
    anomalies: list[Any],
    output_path: Path,
    account_id: str,
    period: str,
) -> None:
    """Write anomaly alerts to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": account_id,
        "period": period,
        "anomaly_count": len(anomalies),
        "anomalies": [a.as_dict() for a in anomalies],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def dispatch_alerts(
    anomalies: list[Any],
    config: dict,
    account_id: str,
    period: str,
    dry_run: bool = False,
) -> dict[str, bool]:
    """
    Dispatch alerts to all configured channels.

    Returns dict of channel -> success.
    """
    results: dict[str, bool] = {}
    alert_cfg = config.get("alerts", {})

    slack_cfg = alert_cfg.get("slack", {})
    if slack_cfg.get("enabled") and anomalies:
        results["slack"] = send_slack_alert(
            slack_cfg["webhook_url"], anomalies, account_id, period, dry_run=dry_run
        )

    json_cfg = alert_cfg.get("json_output", {})
    if json_cfg.get("enabled"):
        output_path = Path(json_cfg.get("output_path", "output/alerts.json"))
        send_json_alert(anomalies, output_path, account_id, period)
        results["json"] = True

    return results
