"""Thin boto3 wrapper for STS, S3, CloudWatch, and Cost Explorer."""

from __future__ import annotations

import boto3
from botocore.config import Config


_RETRY_CONFIG = Config(retries={"max_attempts": 3, "mode": "standard"})


def get_client(service: str, region: str = "us-east-1", **kwargs):
    """Return a boto3 client for the given service."""
    return boto3.client(service, region_name=region, config=_RETRY_CONFIG, **kwargs)


def get_caller_identity(region: str = "us-east-1") -> dict:
    """Return STS caller identity (account_id, user_id, arn)."""
    sts = get_client("sts", region)
    return sts.get_caller_identity()


def download_s3_object(bucket: str, key: str, dest_path: str, region: str = "us-east-1") -> None:
    """Download S3 object to local path."""
    s3 = get_client("s3", region)
    s3.download_file(bucket, key, dest_path)


def list_s3_objects(bucket: str, prefix: str, region: str = "us-east-1") -> list[dict]:
    """List S3 objects under prefix. Returns list of {key, size, last_modified}."""
    s3 = get_client("s3", region)
    paginator = s3.get_paginator("list_objects_v2")
    objects = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )
    return objects


def get_cloudwatch_metric_stats(
    namespace: str,
    metric_name: str,
    dimensions: list[dict],
    start_time: str,
    end_time: str,
    period: int,
    stat: str,
    region: str = "us-east-1",
) -> list[dict]:
    """Return CloudWatch metric datapoints."""
    from datetime import datetime

    cw = get_client("cloudwatch", region)
    response = cw.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=datetime.fromisoformat(start_time),
        EndTime=datetime.fromisoformat(end_time),
        Period=period,
        Statistics=[stat],
    )
    return sorted(response["Datapoints"], key=lambda x: x["Timestamp"])


def get_cost_and_usage(
    start_date: str,
    end_date: str,
    granularity: str = "DAILY",
    group_by: list[dict] | None = None,
    region: str = "us-east-1",
) -> list[dict]:
    """Return Cost Explorer results for the given date range."""
    ce = get_client("ce", region)
    kwargs: dict = {
        "TimePeriod": {"Start": start_date, "End": end_date},
        "Granularity": granularity,
        "Metrics": ["UnblendedCost"],
    }
    if group_by:
        kwargs["GroupBy"] = group_by
    response = ce.get_cost_and_usage(**kwargs)
    return response.get("ResultsByTime", [])
