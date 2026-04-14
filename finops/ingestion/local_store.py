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


class LocalStore:
    """DuckDB-backed local store for CUR data."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize DuckDB connection. Pass None or ':memory:' for in-memory DB."""
        path = str(db_path) if db_path else ":memory:"
        self.conn = duckdb.connect(path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self.conn.execute(_CUR_SCHEMA)

    def insert_cur_rows(self, rows: list[dict[str, Any]]) -> int:
        """Insert enriched CUR rows. Returns count of inserted rows."""
        if not rows:
            return 0
        columns = list(rows[0].keys())
        # Only insert columns that exist in the schema
        schema_cols = [
            "account_id", "usage_start", "usage_end", "usage_date", "product_code",
            "product_name", "usage_type", "operation", "line_item_type", "resource_id",
            "instance_type", "region", "unblended_cost", "unblended_rate", "usage_amount",
            "tag_environment", "tag_team", "tag_project", "service_category",
            "environment", "cost_owner", "cost_project",
        ]
        valid_cols = [c for c in schema_cols if c in columns]
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

    def daily_cost_by_service(self, start_date: str, end_date: str) -> list[dict]:
        """Return daily cost grouped by usage_date and product_name."""
        sql = """
            SELECT usage_date, product_name, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY usage_date, product_name
            ORDER BY usage_date, total_cost DESC
        """
        return self.query(sql, [start_date, end_date])

    def total_daily_cost(self, start_date: str, end_date: str) -> list[dict]:
        """Return total cost per day."""
        sql = """
            SELECT usage_date, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY usage_date
            ORDER BY usage_date
        """
        return self.query(sql, [start_date, end_date])

    def cost_by_team(self, start_date: str, end_date: str) -> list[dict]:
        """Return cost grouped by cost_owner (team tag)."""
        sql = """
            SELECT cost_owner, SUM(unblended_cost) AS total_cost
            FROM cur
            WHERE usage_date >= ? AND usage_date <= ?
            GROUP BY cost_owner
            ORDER BY total_cost DESC
        """
        return self.query(sql, [start_date, end_date])

    def row_count(self) -> int:
        """Return total rows in cur table."""
        result = self.query("SELECT COUNT(*) AS cnt FROM cur")
        return result[0]["cnt"] if result else 0

    def close(self) -> None:
        """Close the DuckDB connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
