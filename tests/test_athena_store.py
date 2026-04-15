"""Tests for AthenaStore — mocked via moto."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from finops.ingestion.athena_store import AthenaStore


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_store() -> AthenaStore:
    return AthenaStore(
        workgroup="test-wg",
        database="finops_db",
        output_location="s3://test-bucket/results/",
        region="us-east-1",
    )


def _athena_response(execution_id: str) -> dict:
    """Minimal start_query_execution response."""
    return {"QueryExecutionId": execution_id}


def _status_response(execution_id: str, state: str) -> dict:
    return {
        "QueryExecution": {
            "QueryExecutionId": execution_id,
            "Status": {"State": state, "StateChangeReason": ""},
        }
    }


def _results_response(headers: list[str], rows: list[list[str]]) -> dict:
    """Build a minimal Athena get_query_results page."""
    header_row = {"Data": [{"VarCharValue": h} for h in headers]}
    data_rows = [
        {"Data": [{"VarCharValue": v} for v in row]}
        for row in rows
    ]
    return {
        "ResultSet": {
            "Rows": [header_row, *data_rows],
        }
    }


# ── Constructor ───────────────────────────────────────────────────────────────

def test_store_constructor_stores_config() -> None:
    store = _make_store()
    assert store.workgroup == "test-wg"
    assert store.database == "finops_db"
    assert store.output_location == "s3://test-bucket/results/"


# ── query() ───────────────────────────────────────────────────────────────────

def test_query_returns_rows() -> None:
    store = _make_store()
    eid = "exec-001"

    mock_client = MagicMock()
    mock_client.start_query_execution.return_value = _athena_response(eid)
    mock_client.get_query_execution.return_value = _status_response(eid, "SUCCEEDED")

    paginator = MagicMock()
    paginator.paginate.return_value = [
        _results_response(
            ["usage_date", "total_cost"],
            [["2024-01-01", "150.50"], ["2024-01-02", "200.00"]],
        )
    ]
    mock_client.get_paginator.return_value = paginator

    store._client = mock_client

    rows = store.query("SELECT 1")

    assert len(rows) == 2
    assert rows[0]["usage_date"] == "2024-01-01"
    assert rows[0]["total_cost"] == "150.50"
    assert rows[1]["total_cost"] == "200.00"


def test_query_raises_on_failed_execution() -> None:
    store = _make_store()
    eid = "exec-fail"

    mock_client = MagicMock()
    mock_client.start_query_execution.return_value = _athena_response(eid)
    mock_client.get_query_execution.return_value = _status_response(eid, "FAILED")
    store._client = mock_client

    with pytest.raises(RuntimeError, match="FAILED"):
        store.query("SELECT broken")


def test_query_raises_on_cancelled() -> None:
    store = _make_store()
    eid = "exec-cancel"

    mock_client = MagicMock()
    mock_client.start_query_execution.return_value = _athena_response(eid)
    mock_client.get_query_execution.return_value = _status_response(eid, "CANCELLED")
    store._client = mock_client

    with pytest.raises(RuntimeError, match="CANCELLED"):
        store.query("SELECT 1")


def test_query_timeout() -> None:
    """If query never finishes, TimeoutError is raised."""
    from finops.ingestion import athena_store as mod

    store = _make_store()
    eid = "exec-hang"

    mock_client = MagicMock()
    mock_client.start_query_execution.return_value = _athena_response(eid)
    mock_client.get_query_execution.return_value = _status_response(eid, "RUNNING")
    store._client = mock_client

    original_max = mod._MAX_WAIT
    original_interval = mod._POLL_INTERVAL
    mod._MAX_WAIT = 1
    mod._POLL_INTERVAL = 2  # interval > max → exits immediately
    try:
        with pytest.raises(TimeoutError):
            store.query("SELECT SLEEP(100)")
    finally:
        mod._MAX_WAIT = original_max
        mod._POLL_INTERVAL = original_interval


# ── start_query ───────────────────────────────────────────────────────────────

def test_start_query_passes_correct_params() -> None:
    store = _make_store()
    mock_client = MagicMock()
    mock_client.start_query_execution.return_value = {"QueryExecutionId": "exec-xyz"}
    store._client = mock_client

    eid = store._start_query("SELECT 1")

    assert eid == "exec-xyz"
    mock_client.start_query_execution.assert_called_once_with(
        QueryString="SELECT 1",
        QueryExecutionContext={"Database": "finops_db"},
        WorkGroup="test-wg",
        ResultConfiguration={"OutputLocation": "s3://test-bucket/results/"},
    )


# ── fetch_results pagination ───────────────────────────────────────────────────

def test_fetch_results_multipage() -> None:
    """Paginator with multiple pages returns all rows."""
    store = _make_store()

    page1 = _results_response(["col_a"], [["row1"], ["row2"]])
    # page2 has no header row — paginator yields continuation pages without headers
    page2 = {"ResultSet": {"Rows": [{"Data": [{"VarCharValue": "row3"}]}]}}

    paginator = MagicMock()
    paginator.paginate.return_value = [page1, page2]

    mock_client = MagicMock()
    mock_client.get_paginator.return_value = paginator
    store._client = mock_client

    rows = store._fetch_results("exec-page")

    # page1: 2 data rows; page2: 1 row (no header stripping on continuation pages)
    assert len(rows) == 3


# ── high-level query helpers ──────────────────────────────────────────────────

def test_total_daily_cost_query_contains_dates() -> None:
    store = _make_store()
    captured_sql: list[str] = []

    def fake_query(sql: str) -> list[dict]:
        captured_sql.append(sql)
        return []

    store.query = fake_query  # type: ignore[method-assign]
    store.total_daily_cost("2024-01-01", "2024-01-31")

    assert "2024-01-01" in captured_sql[0]
    assert "2024-01-31" in captured_sql[0]
    assert "SUM" in captured_sql[0]


def test_top_services_uses_limit() -> None:
    store = _make_store()
    captured_sql: list[str] = []

    def fake_query(sql: str) -> list[dict]:
        captured_sql.append(sql)
        return []

    store.query = fake_query  # type: ignore[method-assign]
    store.top_services("2024-01-01", "2024-01-31", limit=5)

    assert "LIMIT 5" in captured_sql[0]


def test_cost_by_team_groups_by_tag() -> None:
    store = _make_store()
    captured_sql: list[str] = []

    def fake_query(sql: str) -> list[dict]:
        captured_sql.append(sql)
        return []

    store.query = fake_query  # type: ignore[method-assign]
    store.cost_by_team("2024-01-01", "2024-01-31")

    assert "resource_tags_user_team" in captured_sql[0]
    assert "untagged" in captured_sql[0]
