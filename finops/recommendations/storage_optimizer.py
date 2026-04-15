"""S3 lifecycle and EBS type optimization recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_RULES_PATH = Path(__file__).parent.parent / "config" / "rules" / "rightsizing_rules.yaml"


@dataclass
class StorageRecommendation:
    rule_id: str
    rule_name: str
    resource_id: str
    resource_type: str      # ebs | s3
    region: str
    action: str
    current_config: str
    recommended_config: str
    monthly_cost_usd: float
    estimated_savings_usd: float
    confidence: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "region": self.region,
            "action": self.action,
            "current_config": self.current_config,
            "recommended_config": self.recommended_config,
            "monthly_cost_usd": round(self.monthly_cost_usd, 2),
            "estimated_savings_usd": round(self.estimated_savings_usd, 2),
            "confidence": self.confidence,
            "reason": self.reason,
        }


def load_storage_rules(rules_path: Path = _DEFAULT_RULES_PATH) -> list[dict]:
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    return [r for r in data.get("rules", {}).get("storage", []) if r.get("enabled", True)]


def analyze_ebs_volumes(
    volumes: list[dict[str, Any]],
    rules_path: Path = _DEFAULT_RULES_PATH,
) -> list[StorageRecommendation]:
    """
    Analyze EBS volumes and return optimization recommendations.

    Each volume dict must have:
      volume_id, volume_type, size_gb, region, monthly_cost_usd,
      metrics: {VolumeReadOps: {average}, VolumeWriteOps: {average}}
    """
    rules = [r for r in load_storage_rules(rules_path) if r["id"] == "ebs_low_utilization"]
    recommendations: list[StorageRecommendation] = []

    for vol in volumes:
        for rule in rules:
            rec = _evaluate_ebs(vol, rule)
            if rec:
                recommendations.append(rec)

    return sorted(recommendations, key=lambda r: r.estimated_savings_usd, reverse=True)


def analyze_s3_buckets(
    buckets: list[dict[str, Any]],
    rules_path: Path = _DEFAULT_RULES_PATH,
) -> list[StorageRecommendation]:
    """
    Analyze S3 buckets and return lifecycle recommendations.

    Each bucket dict must have:
      bucket_name, region, monthly_cost_usd,
      has_lifecycle_policy (bool), size_gb, growth_rate_pct
    """
    rules = [r for r in load_storage_rules(rules_path) if r["id"] == "s3_missing_lifecycle"]
    recommendations: list[StorageRecommendation] = []

    for bucket in buckets:
        for rule in rules:
            rec = _evaluate_s3(bucket, rule)
            if rec:
                recommendations.append(rec)

    return sorted(recommendations, key=lambda r: r.estimated_savings_usd, reverse=True)


def _evaluate_ebs(volume: dict, rule: dict) -> StorageRecommendation | None:
    metrics = volume.get("metrics", {})
    read_ops = metrics.get("VolumeReadOps", {}).get("average", 0)
    write_ops = metrics.get("VolumeWriteOps", {}).get("average", 0)
    total_iops = read_ops + write_ops
    threshold_pct = rule.get("threshold_pct", 40)
    monthly_cost = volume.get("monthly_cost_usd", 0.0)
    volume_type = volume.get("volume_type", "gp2")

    # Low utilization heuristic: total IOPS < threshold compared to provisioned IOPS
    # For gp2: baseline is 3 IOPS/GB. Use 100 IOPS as minimum meaningful baseline.
    size_gb = volume.get("size_gb", 1)
    provisioned_iops = max(size_gb * 3, 100)
    utilization_pct = (total_iops / provisioned_iops * 100) if provisioned_iops > 0 else 100

    if utilization_pct >= threshold_pct:
        return None

    savings_pct = rule.get("savings_estimate_pct", 20) / 100
    action = rule.get("action", "recommend_gp3_or_delete")

    if total_iops < 1.0:
        # Likely unused — recommend deletion
        action_str = "delete"
        rec_config = "Delete (no I/O detected)"
        confidence = "medium"
        savings = monthly_cost
    elif volume_type == "gp2":
        action_str = "migrate_to_gp3"
        rec_config = "gp3 (same IOPS, 20% cheaper)"
        confidence = "high"
        savings = monthly_cost * 0.2
    else:
        action_str = "review"
        rec_config = f"Review: {volume_type} with low utilization"
        confidence = "low"
        savings = monthly_cost * savings_pct

    return StorageRecommendation(
        rule_id=rule["id"],
        rule_name=rule["name"],
        resource_id=volume.get("volume_id", ""),
        resource_type="ebs",
        region=volume.get("region", ""),
        action=action_str,
        current_config=f"{volume_type}, {size_gb}GB",
        recommended_config=rec_config,
        monthly_cost_usd=monthly_cost,
        estimated_savings_usd=savings,
        confidence=confidence,
        reason=(
            f"Volume utilization {utilization_pct:.1f}% (IOPS avg: {total_iops:.0f}) "
            f"is below {threshold_pct}% threshold."
        ),
    )


def _evaluate_s3(bucket: dict, rule: dict) -> StorageRecommendation | None:
    if bucket.get("has_lifecycle_policy", False):
        return None
    monthly_cost = bucket.get("monthly_cost_usd", 0.0)
    if monthly_cost <= 0:
        return None
    growth_rate = bucket.get("growth_rate_pct", 0)
    savings_pct = rule.get("savings_estimate_pct", 15) / 100

    return StorageRecommendation(
        rule_id=rule["id"],
        rule_name=rule["name"],
        resource_id=bucket.get("bucket_name", ""),
        resource_type="s3",
        region=bucket.get("region", ""),
        action="add_lifecycle_policy",
        current_config=f"No lifecycle policy, {bucket.get('size_gb', 0):.1f}GB",
        recommended_config="Add lifecycle: IA after 30d, Glacier after 90d",
        monthly_cost_usd=monthly_cost,
        estimated_savings_usd=monthly_cost * savings_pct,
        confidence="medium" if growth_rate > 10 else "low",
        reason=(
            f"Bucket has no lifecycle policy. "
            f"Size: {bucket.get('size_gb', 0):.1f}GB, "
            f"growth rate: {growth_rate:.1f}%/month."
        ),
    )
