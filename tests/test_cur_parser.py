"""Tests for CUR parser (CSV + GZIP) and enricher."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from finops.ingestion.cur_parser import parse_cur_from_file, parse_cur_csv
from finops.ingestion.cur_enricher import enrich_cur_rows


# ── Parser ────────────────────────────────────────────────────────────────────

def test_parse_cur_returns_list(sample_cur_path: Path):
    rows = parse_cur_from_file(sample_cur_path)
    assert isinstance(rows, list)
    assert len(rows) > 0


def test_parse_cur_normalized_keys(sample_cur_rows: list[dict]):
    """Parsed rows must have normalized keys — no raw CUR column names."""
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
    """$0 Usage rows must be filtered out."""
    zero_usage = [
        r for r in sample_cur_rows
        if r["unblended_cost"] == 0.0 and r["line_item_type"] == "Usage"
    ]
    assert len(zero_usage) == 0


def test_parse_cur_csv_empty():
    rows = parse_cur_csv("lineItem/UsageAccountId,lineItem/UnblendedCost\n")
    assert rows == []


def test_parse_cur_gzip(sample_cur_path: Path, tmp_path: Path):
    """parse_cur_from_file must transparently handle GZIP-compressed CSV."""
    raw = sample_cur_path.read_bytes()
    gz_path = tmp_path / "sample.csv.gz"
    gz_path.write_bytes(gzip.compress(raw))

    rows_plain = parse_cur_from_file(sample_cur_path)
    rows_gzip = parse_cur_from_file(gz_path)

    assert len(rows_plain) == len(rows_gzip)
    assert rows_plain[0]["account_id"] == rows_gzip[0]["account_id"]


def test_parse_cur_all_accounts_present(sample_cur_rows: list[dict]):
    accounts = {r["account_id"] for r in sample_cur_rows}
    assert "123456789012" in accounts


# ── Enricher ──────────────────────────────────────────────────────────────────

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


def test_enrich_unknown_product_maps_to_other(sample_cur_rows: list[dict]):
    """Products not in the map should get 'Other' category."""
    fake_row = dict(sample_cur_rows[0])
    fake_row["product_code"] = "UnknownProduct999"
    enriched = enrich_cur_rows([fake_row])
    assert enriched[0]["service_category"] == "Other"


def test_enrich_production_tag_preserved(sample_cur_rows: list[dict]):
    enriched = enrich_cur_rows(sample_cur_rows)
    prod_rows = [r for r in enriched if r.get("tag_environment") == "production"]
    assert all(r["environment"] == "production" for r in prod_rows)
