"""Enrich parsed CUR rows with tag-based cost allocation categories."""

from __future__ import annotations

from typing import Any


# Maps known product codes to human-friendly service categories
_SERVICE_CATEGORY_MAP = {
    "AmazonEC2": "Compute",
    "AmazonEKS": "Compute",
    "AWSLambda": "Compute",
    "AmazonS3": "Storage",
    "AmazonEBS": "Storage",
    "AmazonRDS": "Database",
    "AmazonDynamoDB": "Database",
    "AmazonElastiCache": "Database",
    "AmazonCloudFront": "Networking",
    "AmazonVPC": "Networking",
    "AWSDataTransfer": "Networking",
    "AmazonCloudWatch": "Observability",
    "AWSXRay": "Observability",
    "AmazonSNS": "Messaging",
    "AmazonSQS": "Messaging",
    "AWSSecretsManager": "Security",
    "AWSKMS": "Security",
    "AWSSupport": "Support",
}


def _infer_environment(row: dict[str, Any]) -> str:
    """Infer environment from tag or resource naming conventions."""
    env = row.get("tag_environment", "").lower()
    if env:
        return env
    resource_id = row.get("resource_id", "").lower()
    for keyword in ("prod", "production"):
        if keyword in resource_id:
            return "production"
    for keyword in ("staging", "stage"):
        if keyword in resource_id:
            return "staging"
    for keyword in ("dev", "develop"):
        if keyword in resource_id:
            return "development"
    return "unknown"


def enrich_cur_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add derived fields to each CUR row for cost allocation."""
    enriched = []
    for row in rows:
        r = dict(row)
        product_code = r.get("product_code", "")
        r["service_category"] = _SERVICE_CATEGORY_MAP.get(product_code, "Other")
        r["environment"] = _infer_environment(r)
        team = r.get("tag_team", "").strip()
        r["cost_owner"] = team if team else "untagged"
        project = r.get("tag_project", "").strip()
        r["cost_project"] = project if project else "unallocated"
        # Derive date string from usage_start (format: 2024-01-15T00:00:00Z)
        usage_start = r.get("usage_start", "")
        r["usage_date"] = usage_start[:10] if len(usage_start) >= 10 else ""
        enriched.append(r)
    return enriched
