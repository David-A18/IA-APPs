"""Top movers: services with largest absolute/percentage cost change between periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from finops.ingestion.local_store import LocalStore


@dataclass
class TopMover:
    service: str
    current_cost: float
    previous_cost: float
    delta_usd: float
    delta_pct: float | None  # None if previous_cost was 0 (new service)
    is_new: bool  # True if service didn't exist in previous period

    def as_dict(self) -> dict:
        return {
            "service": self.service,
            "current_cost_usd": round(self.current_cost, 4),
            "previous_cost_usd": round(self.previous_cost, 4),
            "delta_usd": round(self.delta_usd, 4),
            "delta_pct": round(self.delta_pct, 2) if self.delta_pct is not None else None,
            "is_new": self.is_new,
        }


def compute_top_movers(
    store: LocalStore,
    current_start: str,
    current_end: str,
    previous_start: str | None = None,
    previous_end: str | None = None,
    top_n: int = 10,
    min_delta_usd: float = 1.0,
) -> dict[str, list[dict]]:
    """
    Compare service costs between two periods and return top movers.

    If previous_start/end not provided, uses a window of equal length before current period.
    Returns dict with 'by_absolute' and 'by_percentage' lists.
    """
    cur_start_d = date.fromisoformat(current_start)
    cur_end_d = date.fromisoformat(current_end)
    period_days = (cur_end_d - cur_start_d).days or 1

    if not previous_start or not previous_end:
        prev_end_d = cur_start_d - timedelta(days=1)
        prev_start_d = prev_end_d - timedelta(days=period_days - 1)
        previous_start = prev_start_d.isoformat()
        previous_end = prev_end_d.isoformat()

    current_rows = store.daily_cost_by_service(current_start, current_end)
    previous_rows = store.daily_cost_by_service(previous_start, previous_end)

    current_map = _aggregate_by_service(current_rows)
    previous_map = _aggregate_by_service(previous_rows)

    movers: list[TopMover] = []
    all_services = set(current_map) | set(previous_map)

    for service in all_services:
        curr = current_map.get(service, 0.0)
        prev = previous_map.get(service, 0.0)
        delta_usd = curr - prev

        if abs(delta_usd) < min_delta_usd:
            continue

        is_new = service not in previous_map
        delta_pct = ((curr - prev) / prev * 100) if prev > 0 else None

        movers.append(TopMover(
            service=service,
            current_cost=curr,
            previous_cost=prev,
            delta_usd=delta_usd,
            delta_pct=delta_pct,
            is_new=is_new,
        ))

    by_absolute = sorted(movers, key=lambda m: m.delta_usd, reverse=True)[:top_n]
    by_percentage = sorted(
        [m for m in movers if m.delta_pct is not None],
        key=lambda m: m.delta_pct,  # type: ignore[arg-type]
        reverse=True,
    )[:top_n]

    return {
        "period": {
            "current": {"start": current_start, "end": current_end},
            "previous": {"start": previous_start, "end": previous_end},
        },
        "by_absolute": [m.as_dict() for m in by_absolute],
        "by_percentage": [m.as_dict() for m in by_percentage],
    }


def _aggregate_by_service(rows: list[dict]) -> dict[str, float]:
    """Sum total_cost per product_name across all dates."""
    result: dict[str, float] = {}
    for row in rows:
        svc = row.get("product_name", "")
        result[svc] = result.get(svc, 0.0) + row.get("total_cost", 0.0)
    return result
