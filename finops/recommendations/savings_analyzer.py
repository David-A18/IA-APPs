"""Reserved Instance and Savings Plans analysis for stable workloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from finops.ingestion.local_store import LocalStore


# Approximate RI/SP discount rates vs on-demand
_SAVINGS_RATES = {
    "1yr_no_upfront": 0.30,
    "1yr_partial_upfront": 0.38,
    "1yr_all_upfront": 0.42,
    "3yr_no_upfront": 0.45,
    "3yr_partial_upfront": 0.54,
    "3yr_all_upfront": 0.60,
}

# Minimum daily cost stability ratio to qualify for RI/SP recommendation
_STABILITY_THRESHOLD = 0.80  # < 20% CV = stable


@dataclass
class SavingsPlanRecommendation:
    service: str
    commitment_type: str        # savings_plan | reserved_instance
    term: str                   # 1yr | 3yr
    payment_option: str         # no_upfront | partial_upfront | all_upfront
    avg_daily_cost_usd: float
    monthly_commitment_usd: float
    estimated_monthly_savings_usd: float
    discount_rate_pct: float
    stability_score: float      # 0-1, higher = more stable
    confidence: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "commitment_type": self.commitment_type,
            "term": self.term,
            "payment_option": self.payment_option,
            "avg_daily_cost_usd": round(self.avg_daily_cost_usd, 2),
            "monthly_commitment_usd": round(self.monthly_commitment_usd, 2),
            "estimated_monthly_savings_usd": round(self.estimated_monthly_savings_usd, 2),
            "discount_rate_pct": round(self.discount_rate_pct * 100, 1),
            "stability_score": round(self.stability_score, 3),
            "confidence": self.confidence,
            "reason": self.reason,
        }


def analyze_savings_opportunities(
    store: LocalStore,
    start_date: str,
    end_date: str,
    min_monthly_cost: float = 50.0,
) -> list[SavingsPlanRecommendation]:
    """
    Identify services with stable usage that qualify for RI/SP commitments.

    min_monthly_cost: skip services below this monthly threshold (not worth committing).
    """
    rows = store.daily_cost_by_service(start_date, end_date)
    service_daily: dict[str, list[float]] = {}
    for row in rows:
        svc = row["product_name"]
        service_daily.setdefault(svc, []).append(row["total_cost"])

    recommendations: list[SavingsPlanRecommendation] = []
    for svc, daily_costs in service_daily.items():
        if len(daily_costs) < 7:
            continue  # Not enough data
        avg = sum(daily_costs) / len(daily_costs)
        monthly_avg = avg * 30
        if monthly_avg < min_monthly_cost:
            continue

        stability = _compute_stability(daily_costs)
        if stability < _STABILITY_THRESHOLD:
            continue  # Too variable for commitment

        rec = _make_recommendation(svc, avg, monthly_avg, stability)
        if rec:
            recommendations.append(rec)

    return sorted(recommendations, key=lambda r: r.estimated_monthly_savings_usd, reverse=True)


def _compute_stability(daily_costs: list[float]) -> float:
    """Compute stability score (1 - CV). CV = std/mean. Higher = more stable."""
    if not daily_costs or len(daily_costs) < 2:
        return 0.0
    mean = sum(daily_costs) / len(daily_costs)
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in daily_costs) / len(daily_costs)
    std = variance ** 0.5
    cv = std / mean
    return max(0.0, min(1.0, 1.0 - cv))


def _make_recommendation(
    service: str,
    avg_daily: float,
    monthly_avg: float,
    stability: float,
) -> SavingsPlanRecommendation | None:
    # Choose term based on stability score
    if stability >= 0.95:
        term = "3yr"
        payment = "partial_upfront"
    elif stability >= 0.85:
        term = "1yr"
        payment = "partial_upfront"
    else:
        term = "1yr"
        payment = "no_upfront"

    rate_key = f"{term}_{payment}"
    discount_rate = _SAVINGS_RATES.get(rate_key, 0.30)
    savings_usd = monthly_avg * discount_rate
    commitment = monthly_avg * (1 - discount_rate)

    # Compute type: EC2 → RI, others → Savings Plans
    commitment_type = "reserved_instance" if "EC2" in service or "RDS" in service else "savings_plan"

    confidence = "high" if stability >= 0.92 else "medium"

    return SavingsPlanRecommendation(
        service=service,
        commitment_type=commitment_type,
        term=term,
        payment_option=payment,
        avg_daily_cost_usd=avg_daily,
        monthly_commitment_usd=commitment,
        estimated_monthly_savings_usd=savings_usd,
        discount_rate_pct=discount_rate,
        stability_score=stability,
        confidence=confidence,
        reason=(
            f"Service has {stability:.0%} stability over evaluation period. "
            f"Monthly avg ${monthly_avg:.2f} qualifies for {term} {payment.replace('_', ' ')} "
            f"at {discount_rate*100:.0f}% discount."
        ),
    )
