"""Parse AWS Cost and Usage Report (CUR) from local CSV or S3."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any


# Canonical CUR column mappings (subset used by this tool)
_COLUMN_MAP = {
    "lineItem/UsageAccountId": "account_id",
    "lineItem/UsageStartDate": "usage_start",
    "lineItem/UsageEndDate": "usage_end",
    "lineItem/ProductCode": "product_code",
    "lineItem/UsageType": "usage_type",
    "lineItem/Operation": "operation",
    "lineItem/LineItemType": "line_item_type",
    "lineItem/UnblendedCost": "unblended_cost",
    "lineItem/UnblendedRate": "unblended_rate",
    "lineItem/UsageAmount": "usage_amount",
    "lineItem/ResourceId": "resource_id",
    "product/ProductName": "product_name",
    "product/region": "region",
    "product/instanceType": "instance_type",
    "resourceTags/user:Environment": "tag_environment",
    "resourceTags/user:Team": "tag_team",
    "resourceTags/user:Project": "tag_project",
}


def _normalize_row(row: dict[str, str]) -> dict[str, Any]:
    """Map raw CUR column names to normalized keys and coerce types."""
    normalized: dict[str, Any] = {}
    for raw_col, norm_col in _COLUMN_MAP.items():
        value = row.get(raw_col, "")
        if norm_col in ("unblended_cost", "unblended_rate", "usage_amount"):
            try:
                normalized[norm_col] = float(value) if value else 0.0
            except ValueError:
                normalized[norm_col] = 0.0
        else:
            normalized[norm_col] = value.strip()
    return normalized


def parse_cur_csv(content: str) -> list[dict[str, Any]]:
    """Parse CUR CSV content string into list of normalized row dicts."""
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for raw_row in reader:
        normalized = _normalize_row(raw_row)
        # Skip $0 usage lines (credits, taxes kept intentionally)
        if normalized["line_item_type"] not in ("Credit",) and normalized["unblended_cost"] == 0.0:
            continue
        rows.append(normalized)
    return rows


def parse_cur_from_file(path: Path) -> list[dict[str, Any]]:
    """Parse CUR CSV from local file path."""
    content = path.read_text(encoding="utf-8")
    return parse_cur_csv(content)


def parse_cur_from_s3(bucket: str, key: str, region: str = "us-east-1") -> list[dict[str, Any]]:
    """Download CUR CSV from S3 and parse it."""
    import boto3

    s3 = boto3.client("s3", region_name=region)
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    return parse_cur_csv(content)
