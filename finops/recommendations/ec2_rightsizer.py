"""EC2 rightsizing recommendations from CloudWatch metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_RULES_PATH = Path(__file__).parent.parent / "config" / "rules" / "rightsizing_rules.yaml"

# EC2 instance family downgrade map (one size smaller, same family)
_DOWNSIZE_MAP: dict[str, str] = {
    "t3.xlarge": "t3.large",
    "t3.large": "t3.medium",
    "t3.medium": "t3.small",
    "t3.small": "t3.micro",
    "m5.4xlarge": "m5.2xlarge",
    "m5.2xlarge": "m5.xlarge",
    "m5.xlarge": "m5.large",
    "m5.large": "m5.medium",  # hypothetical
    "c5.4xlarge": "c5.2xlarge",
    "c5.2xlarge": "c5.xlarge",
    "c5.xlarge": "c5.large",
    "r5.4xlarge": "r5.2xlarge",
    "r5.2xlarge": "r5.xlarge",
    "r5.xlarge": "r5.large",
}


@dataclass
class EC2Recommendation:
    rule_id: str
    rule_name: str
    instance_id: str
    instance_type: str
    region: str
    action: str
    recommended_type: str | None
    cpu_avg_pct: float | None
    memory_avg_pct: float | None
    monthly_cost_usd: float
    estimated_savings_usd: float
    confidence: str  # high | medium | low
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "instance_id": self.instance_id,
            "instance_type": self.instance_type,
            "region": self.region,
            "action": self.action,
            "recommended_type": self.recommended_type,
            "cpu_avg_pct": self.cpu_avg_pct,
            "memory_avg_pct": self.memory_avg_pct,
            "monthly_cost_usd": round(self.monthly_cost_usd, 2),
            "estimated_savings_usd": round(self.estimated_savings_usd, 2),
            "confidence": self.confidence,
            "reason": self.reason,
        }


def load_ec2_rules(rules_path: Path = _DEFAULT_RULES_PATH) -> list[dict]:
    """Load EC2 rightsizing rules from YAML."""
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    return [r for r in data.get("rules", {}).get("ec2", []) if r.get("enabled", True)]


def analyze_ec2_instances(
    instances: list[dict[str, Any]],
    rules_path: Path = _DEFAULT_RULES_PATH,
) -> list[EC2Recommendation]:
    """
    Analyze EC2 instance metrics and return rightsizing recommendations.

    Each instance dict must have:
      instance_id, instance_type, region, monthly_cost_usd,
      metrics: {CPUUtilization: {average, max}, mem_used_percent: {average, max}}
    """
    rules = load_ec2_rules(rules_path)
    recommendations: list[EC2Recommendation] = []

    for instance in instances:
        for rule in rules:
            rec = _evaluate_instance(instance, rule)
            if rec:
                recommendations.append(rec)

    # Deduplicate: keep highest-priority recommendation per instance
    seen: dict[str, EC2Recommendation] = {}
    priority = {"recommend_stop_or_terminate": 0, "recommend_downsize": 1}
    for rec in recommendations:
        key = rec.instance_id
        if key not in seen or priority.get(rec.action, 9) < priority.get(seen[key].action, 9):
            seen[key] = rec

    return sorted(seen.values(), key=lambda r: r.estimated_savings_usd, reverse=True)


def _evaluate_instance(instance: dict, rule: dict) -> EC2Recommendation | None:
    """Apply a single rule to a single instance. Returns recommendation or None."""
    metrics = instance.get("metrics", {})
    metric_name = rule.get("metric", "CPUUtilization")
    metric_data = metrics.get(metric_name, {})

    cpu_avg = metrics.get("CPUUtilization", {}).get("average")
    mem_avg = metrics.get("mem_used_percent", {}).get("average")
    monthly_cost = instance.get("monthly_cost_usd", 0.0)
    instance_type = instance.get("instance_type", "")
    action = rule.get("action", "")

    if action == "recommend_stop_or_terminate":
        # Idle: CPU p95 < threshold
        if cpu_avg is None:
            return None
        percentile = rule.get("percentile", 95)
        # Approximate: use average as proxy (real impl would need p95 from CW)
        threshold = rule.get("threshold_pct", 5)
        if cpu_avg >= threshold:
            return None
        savings_pct = rule.get("savings_estimate_pct", 100) / 100
        return EC2Recommendation(
            rule_id=rule["id"],
            rule_name=rule["name"],
            instance_id=instance["instance_id"],
            instance_type=instance_type,
            region=instance.get("region", ""),
            action=action,
            recommended_type=None,
            cpu_avg_pct=cpu_avg,
            memory_avg_pct=mem_avg,
            monthly_cost_usd=monthly_cost,
            estimated_savings_usd=monthly_cost * savings_pct,
            confidence="high" if cpu_avg < threshold / 2 else "medium",
            reason=(
                f"CPU avg {cpu_avg:.1f}% is below idle threshold {threshold}% "
                f"(p{percentile} proxy). Instance appears unused."
            ),
        )

    elif action == "recommend_downsize":
        threshold = rule.get("threshold_pct", 20)
        value = metric_data.get("average")
        if value is None:
            return None
        if value >= threshold:
            return None
        recommended_type = _DOWNSIZE_MAP.get(instance_type)
        savings_pct = rule.get("savings_estimate_pct", 30) / 100

        # Confidence: higher if both CPU and memory are low
        if cpu_avg is not None and mem_avg is not None and cpu_avg < threshold and mem_avg < 30:
            confidence = "high"
        elif value < threshold / 2:
            confidence = "medium"
        else:
            confidence = "low"

        return EC2Recommendation(
            rule_id=rule["id"],
            rule_name=rule["name"],
            instance_id=instance["instance_id"],
            instance_type=instance_type,
            region=instance.get("region", ""),
            action=action,
            recommended_type=recommended_type,
            cpu_avg_pct=cpu_avg,
            memory_avg_pct=mem_avg,
            monthly_cost_usd=monthly_cost,
            estimated_savings_usd=monthly_cost * savings_pct,
            confidence=confidence,
            reason=(
                f"{metric_name} avg {value:.1f}% < threshold {threshold}%. "
                f"Consider downsizing{f' to {recommended_type}' if recommended_type else ''}."
            ),
        )

    return None
