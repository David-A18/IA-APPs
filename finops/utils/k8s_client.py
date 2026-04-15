"""Thin kubernetes-client wrapper for pod metrics and resource reads."""

from __future__ import annotations

from typing import Any


def _load_config(kubeconfig: str | None = None, in_cluster: bool = False) -> None:
    """Load kube config from file or in-cluster service account."""
    from kubernetes import config as k8s_config  # type: ignore[import-untyped]

    if in_cluster:
        k8s_config.load_incluster_config()
    elif kubeconfig:
        k8s_config.load_kube_config(config_file=kubeconfig)
    else:
        k8s_config.load_kube_config()  # default ~/.kube/config


def list_pods(
    namespace: str = "",
    label_selector: str = "",
    kubeconfig: str | None = None,
    in_cluster: bool = False,
) -> list[dict[str, Any]]:
    """
    List pods and their resource requests/limits.

    Returns list of dicts with: namespace, pod_name, containers[{name, requests, limits}].
    namespace="" lists across all namespaces.
    """
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]

    _load_config(kubeconfig, in_cluster)
    v1 = k8s_client.CoreV1Api()

    kwargs: dict[str, Any] = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    if namespace:
        pods = v1.list_namespaced_pod(namespace, **kwargs).items
    else:
        pods = v1.list_pod_for_all_namespaces(**kwargs).items

    result = []
    for pod in pods:
        containers = []
        for c in (pod.spec.containers or []):
            req = c.resources.requests or {} if c.resources else {}
            lim = c.resources.limits or {} if c.resources else {}
            containers.append({
                "name": c.name,
                "cpu_request": req.get("cpu", ""),
                "memory_request": req.get("memory", ""),
                "cpu_limit": lim.get("cpu", ""),
                "memory_limit": lim.get("memory", ""),
            })
        result.append({
            "namespace": pod.metadata.namespace,
            "pod_name": pod.metadata.name,
            "node": pod.spec.node_name,
            "phase": pod.status.phase,
            "containers": containers,
        })
    return result


def get_pod_metrics(
    namespace: str = "",
    kubeconfig: str | None = None,
    in_cluster: bool = False,
) -> list[dict[str, Any]]:
    """
    Fetch pod CPU/memory usage from metrics-server (requires metrics-server installed).

    Returns list of dicts with: namespace, pod_name, containers[{name, cpu_millicores, memory_mib}].
    """
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]
    from kubernetes.client.rest import ApiException  # type: ignore[import-untyped]

    _load_config(kubeconfig, in_cluster)
    custom_api = k8s_client.CustomObjectsApi()

    try:
        if namespace:
            response = custom_api.list_namespaced_custom_object(
                "metrics.k8s.io", "v1beta1", namespace, "pods"
            )
        else:
            response = custom_api.list_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "pods"
            )
    except ApiException as e:
        raise RuntimeError(
            f"Failed to fetch pod metrics. Is metrics-server installed? ({e.status}: {e.reason})"
        ) from e

    result = []
    for item in response.get("items", []):
        containers = []
        for c in item.get("containers", []):
            usage = c.get("usage", {})
            containers.append({
                "name": c["name"],
                "cpu_millicores": _parse_cpu(usage.get("cpu", "0")),
                "memory_mib": _parse_memory_mib(usage.get("memory", "0Ki")),
            })
        result.append({
            "namespace": item["metadata"]["namespace"],
            "pod_name": item["metadata"]["name"],
            "containers": containers,
        })
    return result


def build_rightsizing_input(
    pods: list[dict],
    metrics: list[dict],
) -> list[dict[str, Any]]:
    """
    Merge pod resource requests with live metrics into the format expected by k8s_rightsizer.

    Each output dict matches the input schema of analyze_k8s_pods().
    """
    metrics_map = {
        (m["namespace"], m["pod_name"]): m for m in metrics
    }

    result = []
    for pod in pods:
        key = (pod["namespace"], pod["pod_name"])
        pod_metrics = metrics_map.get(key, {})

        for container in pod.get("containers", []):
            cname = container["name"]
            cmetrics = next(
                (c for c in pod_metrics.get("containers", []) if c["name"] == cname),
                {},
            )
            result.append({
                "namespace": pod["namespace"],
                "pod_name": pod["pod_name"],
                "container": cname,
                "cpu_request_millicores": _parse_cpu(container.get("cpu_request", "0")),
                "cpu_usage_avg_millicores": cmetrics.get("cpu_millicores", 0),
                "memory_request_mib": _parse_memory_mib(container.get("memory_request", "0Ki")),
                "memory_usage_avg_mib": cmetrics.get("memory_mib", 0),
            })
    return result


# ── Unit parsers ──────────────────────────────────────────────────────────────

def _parse_cpu(cpu_str: str) -> int:
    """Convert Kubernetes CPU string to millicores. '500m'→500, '1'→1000, '2.5'→2500."""
    cpu_str = cpu_str.strip()
    if cpu_str.endswith("m"):
        return int(float(cpu_str[:-1]))
    try:
        return int(float(cpu_str) * 1000)
    except ValueError:
        return 0


def _parse_memory_mib(mem_str: str) -> int:
    """Convert Kubernetes memory string to MiB. '256Mi'→256, '1Gi'→1024, '512Ki'→0."""
    mem_str = mem_str.strip()
    units = {
        "Ki": 1 / 1024,
        "Mi": 1,
        "Gi": 1024,
        "Ti": 1024 * 1024,
        "K": 1 / 1024,
        "M": 1,
        "G": 1024,
    }
    for suffix, factor in units.items():
        if mem_str.endswith(suffix):
            try:
                return int(float(mem_str[: -len(suffix)]) * factor)
            except ValueError:
                return 0
    try:
        return int(float(mem_str)) // (1024 * 1024)  # bare bytes → MiB
    except ValueError:
        return 0
