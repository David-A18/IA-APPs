"""Markdown report generator using Jinja2 templates."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape([]),  # Markdown — no HTML escaping
        trim_blocks=True,
        lstrip_blocks=True,
    )


def generate_markdown_report(
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
) -> str:
    """Render report.md.j2 template with analysis data."""
    ec2_recs = ec2_recommendations or []
    k8s_recs = k8s_recommendations or []
    storage_recs = storage_recommendations or []
    savings_recs = savings_recommendations or []

    total_savings = (
        sum(r.estimated_savings_usd for r in ec2_recs)
        + sum(r.estimated_savings_usd for r in storage_recs)
        + sum(r.estimated_monthly_savings_usd for r in savings_recs)
    )

    env = _get_env()
    template = env.get_template("report.md.j2")
    return template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        total_cost=total_cost,
        anomalies=[a.as_dict() for a in anomalies],
        ec2_recommendations=[r.as_dict() for r in ec2_recs],
        k8s_recommendations=[r.as_dict() for r in k8s_recs],
        storage_recommendations=[r.as_dict() for r in storage_recs],
        savings_recommendations=[r.as_dict() for r in savings_recs],
        estimated_savings=total_savings,
        unit_economics=unit_economics or {},
    )


def generate_pr_body(
    changes: list[dict],
    estimated_savings: float,
    evaluation_period_days: int,
    metrics_source: str,
    rules_applied: list[str],
) -> str:
    """Render pr_body.md.j2 template for GitHub PR descriptions."""
    env = _get_env()
    template = env.get_template("pr_body.md.j2")
    return template.render(
        changes=changes,
        estimated_savings=estimated_savings,
        evaluation_period_days=evaluation_period_days,
        metrics_source=metrics_source,
        rules_applied=rules_applied,
    )


def write_markdown_report(content: str, output_path: Path) -> None:
    """Write rendered Markdown to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
