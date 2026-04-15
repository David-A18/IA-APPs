"""DuckDB wrapper: create tables, insert CUR data, run SQL queries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


_CUR_SCHEMA = """
CREATE TABLE IF NOT EXISTS cur (
    account_id      VARCHAR,
    usage_start     VARCHAR,
    usage_end       VARCHAR,
    usage_date      VARCHAR,
    product_code    VARCHAR,
    product_name    VARCHAR,
    usage_type      VARCHAR,
    operation       VARCHAR,
    line_item_type  VARCHAR,
    resource_id     VARCHAR,
    instance_type   VARCHAR,
    region          VARCHAR,
    unblended_cost  DOUBLE,
    unblended_rate  DOUBLE,
    usage_amount    DOUBLE,
    tag_environment VARCHAR,
    tag_team        VARCHAR,
    tag_project     VARCHAR,
    service_category VARCHAR,
    environment     VARCHAR,
    cost_owner      VARCHAR,
    cost_project    VARCHAR
)
"""

_SCHEMA_COLS = [
    "account_id", "usage_start", "usage_end", "usage_date", "product_code",
    "product_name", "usage_type", "operation", "line_item_type", "resource_id",
    "instance_type", "region", "unblended_cost", "unblended_rate", "usage_amount",
    "tag_environment", "tag_team", "tag_project", "service_category",
    "environment", "cost_owner", "cost_project",
]


class LocalStore:
    """DuckDB-backed local store for CUR data."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize DuckDB connection. Pass None or ':memory:' for in-memory DB."""
        path = str(db_path) if db_path else ":memory:"
        self.conn = duckdb.connect(path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(_CUR_SCHEMA)

    def insert_cur_rows(self, rows: list[dict[str, Any]]) -> int:
        """Insert enriched CUR rows. Returns count of inserted rows."""
        if not rows:
            return 0
        columns = list(rows[0].keys())
        valid_cols = [c for c in _SCHEMA_COLS if c in columns]
        placeholders = ", ".join(["?"] * len(valid_cols))
        col_list = ", ".join(valid_cols)
        values = [[row.get(c) for c in valid_cols] for row in rows]
        self.conn.executemany(f"INSERT INTO cur ({col_list}) VALUES ({placeholders})", values)
        return len(rows)

    def query(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        """Execute SQL and return list of row dicts."""
        result = self.conn.execute(sql, params or [])
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    # ── Basic queries ────────────────────────────────────────────────────────

    def total_daily_cost(self, start_date: str, end_date: str) -> list[dict]:
        """Total cost per calendar day."""
        return self.query(
            """
            SELECT usage_date, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY usage_date
            ORDER BY usage_date
            """,
            [start_date, end_date],
        )

    def daily_cost_by_service(self, start_date: str, end_date: str) -> list[dict]:
        """Daily cost grouped by product_name."""
        return self.query(
            """
            SELECT usage_date, product_name, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY usage_date, product_name
            ORDER BY usage_date, total_cost DESC
            """,
            [start_date, end_date],
        )

    def cost_by_team(self, start_date: str, end_date: str) -> list[dict]:
        """Cost grouped by team tag (cost_owner)."""
        return self.query(
            """
            SELECT cost_owner, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY cost_owner
            ORDER BY total_cost DESC
            """,
            [start_date, end_date],
        )

    # ── Unit economics ───────────────────────────────────────────────────────

    def cost_by_environment(self, start_date: str, end_date: str) -> list[dict]:
        """Cost grouped by environment (production/staging/dev/unknown)."""
        return self.query(
            """
            SELECT environment, SUM(unblended_cost) AS total_cost,
                   COUNT(*) AS line_items
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY environment
            ORDER BY total_cost DESC
            """,
            [start_date, end_date],
        )

    def cost_by_category(self, start_date: str, end_date: str) -> list[dict]:
        """Cost grouped by service_category (Compute/Storage/Database/etc.)."""
        return self.query(
            """
            SELECT service_category, SUM(unblended_cost) AS total_cost,
                   COUNT(DISTINCT product_name) AS service_count
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY service_category
            ORDER BY total_cost DESC
            """,
            [start_date, end_date],
        )

    def cost_by_region(self, start_date: str, end_date: str) -> list[dict]:
        """Cost grouped by AWS region."""
        return self.query(
            """
            SELECT region, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
              AND region != ''
            GROUP BY region
            ORDER BY total_cost DESC
            """,
            [start_date, end_date],
        )

    def cost_by_project(self, start_date: str, end_date: str) -> list[dict]:
        """Cost grouped by project tag."""
        return self.query(
            """
            SELECT cost_project, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY cost_project
            ORDER BY total_cost DESC
            """,
            [start_date, end_date],
        )

    def top_services(self, start_date: str, end_date: str, limit: int = 10) -> list[dict]:
        """Top N most expensive services in the period."""
        return self.query(
            """
            SELECT product_name, SUM(unblended_cost) AS total_cost,
                   COUNT(*) AS line_items
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY product_name
            ORDER BY total_cost DESC
            LIMIT ?
            """,
            [start_date, end_date, limit],
        )

    def top_resources(self, start_date: str, end_date: str, limit: int = 10) -> list[dict]:
        """Top N most expensive individual resources (resource_id)."""
        return self.query(
            """
            SELECT resource_id, product_name, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
              AND resource_id != ''
            GROUP BY resource_id, product_name
            ORDER BY total_cost DESC
            LIMIT ?
            """,
            [start_date, end_date, limit],
        )

    # ── Time-series analysis ─────────────────────────────────────────────────

    def rolling_avg_daily_cost(self, start_date: str, end_date: str, window: int = 7) -> list[dict]:
        """Daily total cost with N-day rolling average."""
        return self.query(
            f"""
            WITH daily AS (
                SELECT usage_date, SUM(unblended_cost) AS total_cost
                FROM cur
                WHERE usage_date >= ? AND usage_date <= ?
                GROUP BY usage_date
            )
            SELECT usage_date, total_cost,
                   AVG(total_cost) OVER (
                       ORDER BY usage_date
                       ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW
                   ) AS rolling_avg_{window}d
            FROM daily
            ORDER BY usage_date
            """,
            [start_date, end_date],
        )

    def service_cost_by_day(self, service_name: str, start_date: str, end_date: str) -> list[dict]:
        """Daily cost for a specific service (product_name)."""
        return self.query(
            """
            SELECT usage_date, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE product_name = ?
              AND usage_date >= ? AND usage_date <= ?
            GROUP BY usage_date
            ORDER BY usage_date
            """,
            [service_name, start_date, end_date],
        )

    def services_seen_in_range(self, start_date: str, end_date: str) -> set[str]:
        """Return set of product_name values seen in the date range."""
        rows = self.query(
            """
            SELECT DISTINCT product_name FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
              AND product_name != ''
            """,
            [start_date, end_date],
        )
        return {r["product_name"] for r in rows}

    def date_range(self) -> tuple[str, str]:
        """Return (min_date, max_date) across all loaded data."""
        rows = self.query("SELECT MIN(usage_date) AS min_d, MAX(usage_date) AS max_d FROM cur")
        if rows:
            return rows[0]["min_d"] or "", rows[0]["max_d"] or ""
        return "", ""

    # ── Utility ──────────────────────────────────────────────────────────────

    def row_count(self) -> int:
        result = self.query("SELECT COUNT(*) AS cnt FROM cur")
        return result[0]["cnt"] if result else 0

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
