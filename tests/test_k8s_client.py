"""Unit tests for k8s_client helpers (pure logic — no Kubernetes cluster required)."""

from __future__ import annotations

import pytest

from finops.utils.k8s_client import (
    _parse_cpu,
    _parse_memory_mib,
    build_rightsizing_input,
)


# ── CPU parser ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("500m", 500),
    ("1000m", 1000),
    ("1", 1000),
    ("2", 2000),
    ("0.5", 500),
    ("2.5", 2500),
    ("0m", 0),
    ("", 0),
    ("bad", 0),
])
def test_parse_cpu(raw: str, expected: int) -> None:
    assert _parse_cpu(raw) == expected


# ── Memory parser ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("256Mi", 256),
    ("1Gi", 1024),
    ("2Gi", 2048),
    ("512Mi", 512),
    ("1024Ki", 1),      # 1024 Ki = 1 Mi
    ("1M", 1),
    ("1G", 1024),
    ("0Mi", 0),
    ("bad", 0),
    ("", 0),
])
def test_parse_memory_mib(raw: str, expected: int) -> None:
    assert _parse_memory_mib(raw) == expected


# ── build_rightsizing_input ───────────────────────────────────────────────────

def _make_pod(namespace: str, name: str, cpu_req: str = "500m", mem_req: str = "256Mi") -> dict:
    return {
        "namespace": namespace,
        "pod_name": name,
        "node": "node-1",
        "phase": "Running",
        "containers": [
            {
                "name": "app",
                "cpu_request": cpu_req,
                "memory_request": mem_req,
                "cpu_limit": "",
                "memory_limit": "",
            }
        ],
    }


def _make_metric(namespace: str, name: str, cpu_mc: int = 100, mem_mib: int = 64) -> dict:
    return {
        "namespace": namespace,
        "pod_name": name,
        "containers": [{"name": "app", "cpu_millicores": cpu_mc, "memory_mib": mem_mib}],
    }


def test_build_rightsizing_input_basic() -> None:
    pods = [_make_pod("default", "api-abc")]
    metrics = [_make_metric("default", "api-abc", cpu_mc=120, mem_mib=80)]

    result = build_rightsizing_input(pods, metrics)

    assert len(result) == 1
    row = result[0]
    assert row["namespace"] == "default"
    assert row["pod_name"] == "api-abc"
    assert row["container"] == "app"
    assert row["cpu_request_millicores"] == 500
    assert row["cpu_usage_avg_millicores"] == 120
    assert row["memory_request_mib"] == 256
    assert row["memory_usage_avg_mib"] == 80


def test_build_rightsizing_input_missing_metrics() -> None:
    """Pods with no matching metric entry default to 0 usage."""
    pods = [_make_pod("kube-system", "coredns-xyz")]
    metrics: list[dict] = []

    result = build_rightsizing_input(pods, metrics)

    assert len(result) == 1
    row = result[0]
    assert row["cpu_usage_avg_millicores"] == 0
    assert row["memory_usage_avg_mib"] == 0


def test_build_rightsizing_input_multiple_pods() -> None:
    pods = [
        _make_pod("default", "api-1", cpu_req="1", mem_req="1Gi"),
        _make_pod("default", "api-2", cpu_req="250m", mem_req="128Mi"),
    ]
    metrics = [
        _make_metric("default", "api-1", cpu_mc=200, mem_mib=300),
        _make_metric("default", "api-2", cpu_mc=50, mem_mib=30),
    ]

    result = build_rightsizing_input(pods, metrics)

    assert len(result) == 2
    by_pod = {r["pod_name"]: r for r in result}
    assert by_pod["api-1"]["cpu_request_millicores"] == 1000
    assert by_pod["api-1"]["memory_request_mib"] == 1024
    assert by_pod["api-2"]["cpu_request_millicores"] == 250
    assert by_pod["api-2"]["memory_request_mib"] == 128


def test_build_rightsizing_input_cross_namespace_isolation() -> None:
    """Same pod name in different namespaces must not cross-match metrics."""
    pods = [
        _make_pod("dev", "worker"),
        _make_pod("prod", "worker"),
    ]
    metrics = [
        _make_metric("prod", "worker", cpu_mc=900, mem_mib=512),
    ]

    result = build_rightsizing_input(pods, metrics)
    by_ns = {r["namespace"]: r for r in result}

    assert by_ns["prod"]["cpu_usage_avg_millicores"] == 900
    assert by_ns["dev"]["cpu_usage_avg_millicores"] == 0  # no matching metric
