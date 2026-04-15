"""Structured JSON report generator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def generate_json_report(
    account_id: str,
    start_date: str,
    end_date: str,
    total_cost: float,
    anomalies: list[Any],
    ec2_recommendations: list[Any] | None = None,
    k8s_recommendations: list[Any] | None = None,
    storage_recommendations: list[Any] | None = None,
    savings_recommendations: list[Any] | None = None,
    unit_economics: dict | None = None,
    top_movers: dict | None = None,
) -> dict:
    """Build a structured JSON report dict from analysis results."""
    ec2_recs = ec2_recommendations or []
    k8s_recs = k8s_recommendations or []
    storage_recs = storage_recommendations or []
    savings_recs = savings_recommendations or []

    total_savings = (
        sum(r.estimated_savings_usd for r in ec2_recs)
        + sum(r.estimated_savings_usd for r in storage_recs)
        + sum(r.estimated_monthly_savings_usd for r in savings_recs)
    )

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "account_id": account_id,
            "period": {"start": start_date, "end": end_date},
            "tool": "finops-autopilot",
        },
        "summary": {
            "total_cost_usd": round(total_cost, 4),
            "anomalies_detected": len(anomalies),
            "ec2_recommendations": len(ec2_recs),
            "k8s_recommendations": len(k8s_recs),
            "storage_recommendations": len(storage_recs),
            "savings_opportunities": len(savings_recs),
            "estimated_monthly_savings_usd": round(total_savings, 2),
        },
        "anomalies": [a.as_dict() for a in anomalies],
        "recommendations": {
            "ec2": [r.as_dict() for r in ec2_recs],
            "kubernetes": [r.as_dict() for r in k8s_recs],
            "storage": [r.as_dict() for r in storage_recs],
            "savings_plans": [r.as_dict() for r in savings_recs],
        },
        "unit_economics": unit_economics or {},
        "top_movers": top_movers or {},
    }


def write_json_report(report: dict, output_path: Path) -> None:
    """Write JSON report to file, creating parent dirs if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
