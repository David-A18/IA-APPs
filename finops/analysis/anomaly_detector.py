"""Rule-based anomaly detection engine. Reads anomaly_rules.yaml + LocalStore data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from finops.ingestion.local_store import LocalStore

_DEFAULT_RULES_PATH = Path(__file__).parent.parent / "config" / "rules" / "anomaly_rules.yaml"


@dataclass
class AnomalyEvent:
    rule_id: str
    rule_name: str
    severity: str  # low | medium | high
    detected_date: str
    service: str | None
    region: str | None
    current_cost: float
    reference_cost: float  # rolling average or previous period value
    delta_usd: float
    delta_pct: float | None
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "detected_date": self.detected_date,
            "service": self.service,
            "region": self.region,
            "current_cost_usd": round(self.current_cost, 4),
            "reference_cost_usd": round(self.reference_cost, 4),
            "delta_usd": round(self.delta_usd, 4),
            "delta_pct": round(self.delta_pct, 2) if self.delta_pct is not None else None,
            "description": self.description,
        }


def load_rules(rules_path: Path = _DEFAULT_RULES_PATH) -> list[dict]:
    """Load and return anomaly rules from YAML."""
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    return [r for r in data.get("rules", []) if r.get("enabled", True)]


def detect_anomalies(
    store: LocalStore,
    rules_path: Path = _DEFAULT_RULES_PATH,
    end_date: str | None = None,
    lookback_days: int = 7,
) -> list[AnomalyEvent]:
    """
    Run all enabled rules against store data up to end_date.

    end_date defaults to the latest date in the store.
    lookback_days: how many days of history to use as reference baseline.
    """
    min_d, max_d = store.date_range()
    if not max_d:
        return []

    check_date = end_date or max_d
    ref_end = (date.fromisoformat(check_date) - timedelta(days=1)).isoformat()
    ref_start = (date.fromisoformat(check_date) - timedelta(days=lookback_days)).isoformat()

    rules = load_rules(rules_path)
    events: list[AnomalyEvent] = []

    for rule in rules:
        rule_type = rule.get("type")
        if rule_type == "percentage_change":
            events.extend(_check_percentage_change(store, rule, check_date, ref_start, ref_end))
        elif rule_type == "new_entity":
            events.extend(_check_new_entity(store, rule, check_date, ref_start, ref_end))
        elif rule_type == "time_pattern":
            events.extend(_check_time_pattern(store, rule, check_date, ref_start, ref_end))

    return sorted(events, key=lambda e: (_severity_order(e.severity), -e.delta_usd))


# ── Rule handlers ─────────────────────────────────────────────────────────────

def _check_percentage_change(
    store: LocalStore,
    rule: dict,
    check_date: str,
    ref_start: str,
    ref_end: str,
) -> list[AnomalyEvent]:
    """Detect percentage cost change vs rolling average."""
    events: list[AnomalyEvent] = []
    threshold_pct: float = rule.get("threshold_pct", 20)
    min_delta: float = rule.get("min_delta_usd", 0)
    group_by: str | None = rule.get("group_by")  # None = total, "product_name", "region"

    if group_by == "product_name":
        current_rows = store.daily_cost_by_service(check_date, check_date)
        ref_rows = store.daily_cost_by_service(ref_start, ref_end)
        current_map = _aggregate_by(current_rows, group_by, "total_cost")
        ref_map = _aggregate_by(ref_rows, group_by, "total_cost")
        days = max((date.fromisoformat(ref_end) - date.fromisoformat(ref_start)).days, 1)
        groups = set(current_map) & set(ref_map)
        for g in groups:
            curr = current_map[g]
            ref_avg = ref_map[g] / days
            delta_usd = curr - ref_avg
            if ref_avg <= 0 or delta_usd < min_delta:
                continue
            delta_pct = delta_usd / ref_avg * 100
            if delta_pct >= threshold_pct:
                events.append(_make_event(rule, check_date, service=g, region=None,
                                          curr=curr, ref=ref_avg, delta_usd=delta_usd,
                                          delta_pct=delta_pct))

    elif group_by == "region":
        current_rows = store.cost_by_region(check_date, check_date)
        ref_rows = store.cost_by_region(ref_start, ref_end)
        current_map = {r["region"]: r["total_cost"] for r in current_rows}
        ref_raw = {r["region"]: r["total_cost"] for r in ref_rows}
        days = max((date.fromisoformat(ref_end) - date.fromisoformat(ref_start)).days, 1)
        for region in set(current_map) & set(ref_raw):
            curr = current_map[region]
            ref_avg = ref_raw[region] / days
            delta_usd = curr - ref_avg
            if ref_avg <= 0 or delta_usd < min_delta:
                continue
            delta_pct = delta_usd / ref_avg * 100
            if delta_pct >= threshold_pct:
                events.append(_make_event(rule, check_date, service=None, region=region,
                                          curr=curr, ref=ref_avg, delta_usd=delta_usd,
                                          delta_pct=delta_pct))

    else:
        # Total daily cost
        current_rows = store.total_daily_cost(check_date, check_date)
        ref_rows = store.total_daily_cost(ref_start, ref_end)
        curr = sum(r["total_cost"] for r in current_rows)
        days = max((date.fromisoformat(ref_end) - date.fromisoformat(ref_start)).days, 1)
        ref_avg = sum(r["total_cost"] for r in ref_rows) / days
        delta_usd = curr - ref_avg
        if ref_avg > 0 and delta_usd >= min_delta:
            delta_pct = delta_usd / ref_avg * 100
            if delta_pct >= threshold_pct:
                events.append(_make_event(rule, check_date, service=None, region=None,
                                          curr=curr, ref=ref_avg, delta_usd=delta_usd,
                                          delta_pct=delta_pct))

    return events


def _check_new_entity(
    store: LocalStore,
    rule: dict,
    check_date: str,
    ref_start: str,
    ref_end: str,
) -> list[AnomalyEvent]:
    """Detect services that appear in check_date but not in lookback window."""
    events: list[AnomalyEvent] = []
    min_delta: float = rule.get("min_delta_usd", 0)
    current_services = store.services_seen_in_range(check_date, check_date)
    historical_services = store.services_seen_in_range(ref_start, ref_end)
    new_services = current_services - historical_services

    if not new_services:
        return events

    current_rows = store.daily_cost_by_service(check_date, check_date)
    current_map = _aggregate_by(current_rows, "product_name", "total_cost")

    for svc in new_services:
        cost = current_map.get(svc, 0.0)
        if cost < min_delta:
            continue
        events.append(_make_event(rule, check_date, service=svc, region=None,
                                  curr=cost, ref=0.0, delta_usd=cost, delta_pct=None))
    return events


def _check_time_pattern(
    store: LocalStore,
    rule: dict,
    check_date: str,
    ref_start: str,
    ref_end: str,
) -> list[AnomalyEvent]:
    """Detect weekend cost spikes vs weekday average."""
    events: list[AnomalyEvent] = []
    check_day = date.fromisoformat(check_date).weekday()
    expected_days: list[int] = rule.get("expected_days", [0, 1, 2, 3, 4])
    if check_day in expected_days:
        return events  # It's a workday — rule only fires on off-days

    threshold_pct: float = rule.get("threshold_pct", 30)
    min_delta: float = rule.get("min_delta_usd", 0)

    current_rows = store.total_daily_cost(check_date, check_date)
    ref_rows = store.total_daily_cost(ref_start, ref_end)

    weekday_rows = [r for r in ref_rows
                    if date.fromisoformat(r["usage_date"]).weekday() in expected_days]
    if not weekday_rows:
        return events

    curr = sum(r["total_cost"] for r in current_rows)
    ref_avg = sum(r["total_cost"] for r in weekday_rows) / len(weekday_rows)
    delta_usd = curr - ref_avg

    if ref_avg > 0 and delta_usd >= min_delta:
        delta_pct = delta_usd / ref_avg * 100
        if delta_pct >= threshold_pct:
            events.append(_make_event(rule, check_date, service=None, region=None,
                                      curr=curr, ref=ref_avg, delta_usd=delta_usd,
                                      delta_pct=delta_pct))
    return events


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    rule: dict, detected_date: str, service: str | None, region: str | None,
    curr: float, ref: float, delta_usd: float, delta_pct: float | None,
) -> AnomalyEvent:
    subject = service or region or "total"
    pct_str = f"+{delta_pct:.1f}%" if delta_pct is not None else "new service"
    desc = (
        f"{rule['name']}: {subject} cost ${curr:.2f} "
        f"({pct_str}, +${delta_usd:.2f} vs ${ref:.2f} avg)"
    )
    return AnomalyEvent(
        rule_id=rule["id"],
        rule_name=rule["name"],
        severity=rule.get("severity", "medium"),
        detected_date=detected_date,
        service=service,
        region=region,
        current_cost=curr,
        reference_cost=ref,
        delta_usd=delta_usd,
        delta_pct=delta_pct,
        description=desc,
    )


def _aggregate_by(rows: list[dict], key: str, value_col: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        k = row.get(key, "")
        result[k] = result.get(k, 0.0) + row.get(value_col, 0.0)
    return result


def _severity_order(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)
