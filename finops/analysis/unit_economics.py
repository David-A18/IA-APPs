"""Unit economics: cost allocation by team, environment, project, category."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from finops.ingestion.local_store import LocalStore


@dataclass
class UnitEconomicsReport:
    start_date: str
    end_date: str
    total_cost: float
    by_team: list[dict[str, Any]] = field(default_factory=list)
    by_environment: list[dict[str, Any]] = field(default_factory=list)
    by_category: list[dict[str, Any]] = field(default_factory=list)
    by_region: list[dict[str, Any]] = field(default_factory=list)
    by_project: list[dict[str, Any]] = field(default_factory=list)
    top_services: list[dict[str, Any]] = field(default_factory=list)
    top_resources: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": {"start": self.start_date, "end": self.end_date},
            "total_cost_usd": round(self.total_cost, 4),
            "by_team": self.by_team,
            "by_environment": self.by_environment,
            "by_category": self.by_category,
            "by_region": self.by_region,
            "by_project": self.by_project,
            "top_services": self.top_services,
            "top_resources": self.top_resources,
        }


def compute_unit_economics(
    store: LocalStore,
    start_date: str,
    end_date: str,
    top_n: int = 10,
) -> UnitEconomicsReport:
    """Compute full unit economics breakdown for the given date range."""
    daily = store.total_daily_cost(start_date, end_date)
    total_cost = sum(r["total_cost"] for r in daily)

    report = UnitEconomicsReport(
        start_date=start_date,
        end_date=end_date,
        total_cost=total_cost,
        by_team=_add_pct(store.cost_by_team(start_date, end_date), total_cost),
        by_environment=_add_pct(store.cost_by_environment(start_date, end_date), total_cost),
        by_category=_add_pct(store.cost_by_category(start_date, end_date), total_cost),
        by_region=_add_pct(store.cost_by_region(start_date, end_date), total_cost),
        by_project=_add_pct(store.cost_by_project(start_date, end_date), total_cost),
        top_services=store.top_services(start_date, end_date, top_n),
        top_resources=store.top_resources(start_date, end_date, top_n),
    )
    return report


def _add_pct(rows: list[dict], total: float) -> list[dict]:
    """Add pct_of_total field to each row."""
    for row in rows:
        cost = row.get("total_cost", 0.0)
        row["pct_of_total"] = round((cost / total * 100) if total > 0 else 0.0, 2)
        row["total_cost"] = round(cost, 4)
    return rows
