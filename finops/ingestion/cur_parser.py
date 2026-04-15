"""Parse AWS Cost and Usage Report (CUR) from local CSV/Parquet or S3 (GZIP or plain)."""

from __future__ import annotations

import csv
import gzip
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

_ZERO_COST_SKIP_TYPES = {"Usage"}  # skip $0 Usage lines; keep Credits, Taxes, etc.


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


def _should_skip(row: dict[str, Any]) -> bool:
    """Return True for rows that carry no meaningful cost signal."""
    return row["line_item_type"] in _ZERO_COST_SKIP_TYPES and row["unblended_cost"] == 0.0


def parse_cur_csv(content: str) -> list[dict[str, Any]]:
    """Parse CUR CSV content string into list of normalized row dicts."""
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for raw_row in reader:
        normalized = _normalize_row(raw_row)
        if not _should_skip(normalized):
            rows.append(normalized)
    return rows


def parse_cur_from_file(path: Path) -> list[dict[str, Any]]:
    """
    Parse CUR from a local file.

    Supports:
    - Plain CSV (.csv)
    - GZIP-compressed CSV (.csv.gz or .gz)
    - Parquet (.parquet) via DuckDB
    """
    suffix = "".join(path.suffixes).lower()

    if ".parquet" in suffix:
        return _parse_parquet(path)

    raw_bytes = path.read_bytes()
    if raw_bytes[:2] == b"\x1f\x8b":  # GZIP magic bytes
        content = gzip.decompress(raw_bytes).decode("utf-8")
    else:
        content = raw_bytes.decode("utf-8")

    return parse_cur_csv(content)


def parse_cur_from_s3(bucket: str, key: str, region: str = "us-east-1") -> list[dict[str, Any]]:
    """
    Download CUR from S3 and parse it.

    Handles GZIP-compressed CSVs (the default CUR export format).
    For Parquet, downloads to a temp file then uses DuckDB.
    """
    import boto3
    import tempfile

    s3 = boto3.client("s3", region_name=region)
    response = s3.get_object(Bucket=bucket, Key=key)
    raw_bytes: bytes = response["Body"].read()

    if key.endswith(".parquet"):
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = Path(tmp.name)
        try:
            return _parse_parquet(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    # GZIP-compressed CSV (standard CUR export)
    if raw_bytes[:2] == b"\x1f\x8b":
        content = gzip.decompress(raw_bytes).decode("utf-8")
    else:
        content = raw_bytes.decode("utf-8")

    return parse_cur_csv(content)


def _parse_parquet(path: Path) -> list[dict[str, Any]]:
    """Parse CUR Parquet file using DuckDB (no pandas required)."""
    import duckdb

    # Build column expressions: only select columns present in _COLUMN_MAP
    # DuckDB can read parquet directly and return rows as dicts
    conn = duckdb.connect(":memory:")
    try:
        # Read all columns; filter to known ones afterward
        rel = conn.read_parquet(str(path))
        available = {col.lower() for col in rel.columns}
        rows = []
        for raw_row in rel.fetchdf().to_dict("records"):
            # Normalize column names (parquet uses _ instead of /)
            renamed: dict[str, str] = {}
            for k, v in raw_row.items():
                renamed[k] = str(v) if v is not None else ""
            normalized = _normalize_row(renamed)
            if not _should_skip(normalized):
                rows.append(normalized)
        return rows
    finally:
        conn.close()
