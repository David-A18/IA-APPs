"""Tests for LocalStore DuckDB queries (Week 2)."""

import pytest

from finops.ingestion.local_store import LocalStore


def test_store_row_count(in_memory_store):
    assert in_memory_store.row_count() > 0


def test_store_total_daily_cost(in_memory_store):
    rows = in_memory_store.total_daily_cost("2024-01-15", "2024-01-18")
    assert len(rows) >= 1
    for row in rows:
        assert "usage_date" in row
        assert "total_cost" in row
        assert row["total_cost"] > 0


def test_store_daily_cost_by_service(in_memory_store):
    rows = in_memory_store.daily_cost_by_service("2024-01-15", "2024-01-18")
    assert len(rows) > 0
    assert all("product_name" in r for r in rows)


def test_store_cost_by_team(in_memory_store):
    rows = in_memory_store.cost_by_team("2024-01-15", "2024-01-18")
    teams = {r["cost_owner"] for r in rows}
    assert len(teams) > 1


def test_store_cost_by_environment(in_memory_store):
    rows = in_memory_store.cost_by_environment("2024-01-15", "2024-01-18")
    envs = {r["environment"] for r in rows}
    assert "production" in envs or "staging" in envs


def test_store_cost_by_category(in_memory_store):
    rows = in_memory_store.cost_by_category("2024-01-15", "2024-01-18")
    categories = {r["service_category"] for r in rows}
    assert "Compute" in categories
    assert "Storage" in categories


def test_store_cost_by_region(in_memory_store):
    rows = in_memory_store.cost_by_region("2024-01-15", "2024-01-18")
    regions = {r["region"] for r in rows}
    assert len(regions) >= 1


def test_store_cost_by_project(in_memory_store):
    rows = in_memory_store.cost_by_project("2024-01-15", "2024-01-18")
    assert len(rows) >= 1


def test_store_top_services_limit(in_memory_store):
    rows = in_memory_store.top_services("2024-01-15", "2024-01-18", limit=3)
    assert len(rows) <= 3
    costs = [r["total_cost"] for r in rows]
    assert costs == sorted(costs, reverse=True)


def test_store_top_resources(in_memory_store):
    rows = in_memory_store.top_resources("2024-01-15", "2024-01-18", limit=5)
    assert len(rows) <= 5
    assert all("resource_id" in r for r in rows)


def test_store_rolling_avg(in_memory_store):
    rows = in_memory_store.rolling_avg_daily_cost("2024-01-15", "2024-01-18", window=3)
    assert len(rows) >= 1
    assert "rolling_avg_3d" in rows[0]


def test_store_service_cost_by_day(in_memory_store):
    rows = in_memory_store.service_cost_by_day(
        "Amazon Elastic Compute Cloud", "2024-01-15", "2024-01-18"
    )
    assert len(rows) >= 1
    assert all(r["total_cost"] > 0 for r in rows)


def test_store_services_seen_in_range(in_memory_store):
    services = in_memory_store.services_seen_in_range("2024-01-15", "2024-01-18")
    assert isinstance(services, set)
    assert len(services) > 0
    assert "Amazon Elastic Compute Cloud" in services


def test_store_date_range(in_memory_store):
    min_d, max_d = in_memory_store.date_range()
    assert min_d <= max_d
    assert min_d.startswith("2024-01")


def test_store_empty_returns_zero():
    store = LocalStore()
    assert store.row_count() == 0
    assert store.total_daily_cost("2024-01-01", "2024-01-31") == []
    store.close()


def test_store_context_manager(enriched_cur_rows):
    with LocalStore() as store:
        store.insert_cur_rows(enriched_cur_rows)
        assert store.row_count() > 0
    # Connection is closed after context exit — no assertion needed
