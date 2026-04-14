"""Tests for CUR parser and enricher."""

from pathlib import Path

import pytest

from finops.ingestion.cur_parser import parse_cur_from_file, parse_cur_csv
from finops.ingestion.cur_enricher import enrich_cur_rows


def test_parse_cur_returns_list(sample_cur_path: Path):
    rows = parse_cur_from_file(sample_cur_path)
    assert isinstance(rows, list)
    assert len(rows) > 0


def test_parse_cur_normalized_keys(sample_cur_rows: list[dict]):
    """Parsed rows should have normalized keys, not raw CUR column names."""
    row = sample_cur_rows[0]
    assert "account_id" in row
    assert "unblended_cost" in row
    assert "product_code" in row
    assert "lineItem/UsageAccountId" not in row


def test_parse_cur_cost_is_float(sample_cur_rows: list[dict]):
    for row in sample_cur_rows:
        assert isinstance(row["unblended_cost"], float)
        assert row["unblended_cost"] >= 0.0


def test_parse_cur_skips_zero_cost_usage(sample_cur_rows: list[dict]):
    """Rows with 0 cost and Usage line_item_type should be filtered out."""
    zero_usage = [
        r for r in sample_cur_rows
        if r["unblended_cost"] == 0.0 and r["line_item_type"] == "Usage"
    ]
    assert len(zero_usage) == 0


def test_parse_cur_csv_empty():
    rows = parse_cur_csv("lineItem/UsageAccountId,lineItem/UnblendedCost\n")
    assert rows == []


def test_enrich_adds_service_category(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    for row in enriched:
        assert "service_category" in row
        assert row["service_category"] != ""


def test_enrich_adds_environment(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    for row in enriched:
        assert "environment" in row


def test_enrich_adds_cost_owner(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    for row in enriched:
        assert "cost_owner" in row
        assert row["cost_owner"] != ""


def test_enrich_adds_usage_date(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    for row in enriched:
        assert "usage_date" in row
        if row["usage_date"]:
            assert len(row["usage_date"]) == 10  # YYYY-MM-DD


def test_enrich_ec2_maps_to_compute(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    ec2_rows = [r for r in enriched if r["product_code"] == "AmazonEC2"]
    assert all(r["service_category"] == "Compute" for r in ec2_rows)


def test_enrich_s3_maps_to_storage(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    s3_rows = [r for r in enriched if r["product_code"] == "AmazonS3"]
    assert all(r["service_category"] == "Storage" for r in s3_rows)


def test_store_insert_and_count(in_memory_store):
    count = in_memory_store.row_count()
    assert count > 0


def test_store_daily_cost_query(in_memory_store):
    results = in_memory_store.daily_cost_by_service("2024-01-15", "2024-01-18")
    assert isinstance(results, list)
    assert all("usage_date" in r and "total_cost" in r for r in results)


def test_store_cost_by_team(in_memory_store):
    results = in_memory_store.cost_by_team("2024-01-15", "2024-01-18")
    assert isinstance(results, list)
    teams = {r["cost_owner"] for r in results}
    assert "platform" in teams or "backend" in teams or "untagged" in teams
