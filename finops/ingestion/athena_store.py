"""Athena query backend for production — S3 CUR data via AWS Athena."""

from __future__ import annotations

import time
from typing import Any

import boto3
from botocore.config import Config

_RETRY_CONFIG = Config(retries={"max_attempts": 3, "mode": "standard"})
_POLL_INTERVAL = 2  # seconds between status checks
_MAX_WAIT = 300     # 5 minutes timeout per query


class AthenaStore:
    """Query CUR data stored in S3 via AWS Athena."""

    def __init__(
        self,
        workgroup: str,
        database: str,
        output_location: str,
        region: str = "us-east-1",
    ) -> None:
        self.workgroup = workgroup
        self.database = database
        self.output_location = output_location
        self._client = boto3.client("athena", region_name=region, config=_RETRY_CONFIG)

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute SQL against Athena and return results as list of row dicts."""
        execution_id = self._start_query(sql)
        self._wait_for_completion(execution_id)
        return self._fetch_results(execution_id)

    def total_daily_cost(self, start_date: str, end_date: str) -> list[dict]:
        """Total cost per calendar day."""
        return self.query(f"""
            SELECT line_item_usage_start_date AS usage_date,
                   SUM(line_item_unblended_cost) AS total_cost
            FROM cur
            WHERE line_item_usage_start_date >= DATE '{start_date}'
              AND line_item_usage_start_date <  DATE '{end_date}'
            GROUP BY 1
            ORDER BY 1
        """)

    def daily_cost_by_service(self, start_date: str, end_date: str) -> list[dict]:
        """Daily cost grouped by product name."""
        return self.query(f"""
            SELECT DATE_FORMAT(line_item_usage_start_date, '%Y-%m-%d') AS usage_date,
                   product_product_name AS product_name,
                   SUM(line_item_unblended_cost) AS total_cost
            FROM cur
            WHERE line_item_usage_start_date >= DATE '{start_date}'
              AND line_item_usage_start_date <  DATE '{end_date}'
            GROUP BY 1, 2
            ORDER BY 1, 3 DESC
        """)

    def cost_by_team(self, start_date: str, end_date: str) -> list[dict]:
        """Cost grouped by team tag."""
        return self.query(f"""
            SELECT COALESCE(NULLIF(resource_tags_user_team, ''), 'untagged') AS cost_owner,
                   SUM(line_item_unblended_cost) AS total_cost
            FROM cur
            WHERE line_item_usage_start_date >= DATE '{start_date}'
              AND line_item_usage_start_date <  DATE '{end_date}'
            GROUP BY 1
            ORDER BY 2 DESC
        """)

    def top_services(self, start_date: str, end_date: str, limit: int = 10) -> list[dict]:
        """Top N most expensive services."""
        return self.query(f"""
            SELECT product_product_name AS product_name,
                   SUM(line_item_unblended_cost) AS total_cost,
                   COUNT(*) AS line_items
            FROM cur
            WHERE line_item_usage_start_date >= DATE '{start_date}'
              AND line_item_usage_start_date <  DATE '{end_date}'
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT {int(limit)}
        """)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _start_query(self, sql: str) -> str:
        response = self._client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            WorkGroup=self.workgroup,
            ResultConfiguration={"OutputLocation": self.output_location},
        )
        return response["QueryExecutionId"]

    def _wait_for_completion(self, execution_id: str) -> None:
        """Poll until query succeeds or fails. Raises RuntimeError on failure."""
        waited = 0
        while waited < _MAX_WAIT:
            response = self._client.get_query_execution(QueryExecutionId=execution_id)
            state = response["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                return
            if state in ("FAILED", "CANCELLED"):
                reason = response["QueryExecution"]["Status"].get("StateChangeReason", "unknown")
                raise RuntimeError(f"Athena query {execution_id} {state}: {reason}")
            time.sleep(_POLL_INTERVAL)
            waited += _POLL_INTERVAL
        raise TimeoutError(f"Athena query {execution_id} did not complete within {_MAX_WAIT}s")

    def _fetch_results(self, execution_id: str) -> list[dict[str, Any]]:
        """Page through Athena results and return as list of dicts."""
        paginator = self._client.get_paginator("get_query_results")
        pages = paginator.paginate(QueryExecutionId=execution_id)

        rows: list[dict[str, Any]] = []
        headers: list[str] = []

        for page in pages:
            result_rows = page["ResultSet"]["Rows"]
            if not headers:
                headers = [col["VarCharValue"] for col in result_rows[0]["Data"]]
                result_rows = result_rows[1:]  # skip header row
            for row in result_rows:
                values = [col.get("VarCharValue", "") for col in row["Data"]]
                rows.append(dict(zip(headers, values)))

        return rows
