"""K8s requests/limits rightsizing from Prometheus-style metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_RULES_PATH = Path(__file__).parent.parent / "config" / "rules" / "rightsizing_rules.yaml"


@dataclass
class K8sRecommendation:
    rule_id: str
    rule_name: str
    namespace: str
    pod_name: str
    container: str
    resource: str        # cpu | memory
    current_request: str # e.g. "500m" or "256Mi"
    recommended_request: str
    actual_usage_avg: str
    action: str
    estimated_savings_pct: float
    confidence: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "namespace": self.namespace,
            "pod_name": self.pod_name,
            "container": self.container,
            "resource": self.resource,
            "current_request": self.current_request,
            "recommended_request": self.recommended_request,
            "actual_usage_avg": self.actual_usage_avg,
            "action": self.action,
            "estimated_savings_pct": round(self.estimated_savings_pct, 1),
            "confidence": self.confidence,
            "reason": self.reason,
        }


def load_k8s_rules(rules_path: Path = _DEFAULT_RULES_PATH) -> list[dict]:
    """Load K8s rightsizing rules from YAML."""
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    return [r for r in data.get("rules", {}).get("kubernetes", []) if r.get("enabled", True)]


def analyze_k8s_pods(
    pods: list[dict[str, Any]],
    rules_path: Path = _DEFAULT_RULES_PATH,
) -> list[K8sRecommendation]:
    """
    Analyze pod metrics and return rightsizing recommendations.

    Each pod dict must have:
      namespace, pod_name, container,
      cpu_request_millicores, cpu_usage_avg_millicores,
      memory_request_mib, memory_usage_avg_mib
    """
    rules = load_k8s_rules(rules_path)
    recommendations: list[K8sRecommendation] = []

    for pod in pods:
        for rule in rules:
            rec = _evaluate_pod(pod, rule)
            if rec:
                recommendations.append(rec)

    return sorted(recommendations, key=lambda r: r.estimated_savings_pct, reverse=True)


def _evaluate_pod(pod: dict, rule: dict) -> K8sRecommendation | None:
    """Apply a single rule to a single pod. Returns recommendation or None."""
    metric = rule.get("metric", "")
    threshold_ratio: float = rule.get("request_to_usage_ratio", 3.0)
    savings_pct: float = rule.get("savings_estimate_pct", 40)

    if "cpu" in metric:
        request = pod.get("cpu_request_millicores", 0)
        usage = pod.get("cpu_usage_avg_millicores", 0)
        resource = "cpu"
        unit = "m"
        if request <= 0 or usage <= 0:
            return None
        ratio = request / usage
        if ratio < threshold_ratio:
            return None
        # Recommend 20% headroom above actual usage
        recommended = int(usage * 1.2)
        current_str = f"{request}m"
        recommended_str = f"{recommended}m"
        actual_str = f"{usage:.0f}m"

    elif "memory" in metric:
        request = pod.get("memory_request_mib", 0)
        usage = pod.get("memory_usage_avg_mib", 0)
        resource = "memory"
        unit = "Mi"
        if request <= 0 or usage <= 0:
            return None
        ratio = request / usage
        if ratio < threshold_ratio:
            return None
        recommended = int(usage * 1.25)  # 25% headroom for memory
        current_str = f"{request}Mi"
        recommended_str = f"{recommended}Mi"
        actual_str = f"{usage:.0f}Mi"

    else:
        return None

    confidence = "high" if ratio > threshold_ratio * 1.5 else "medium"

    return K8sRecommendation(
        rule_id=rule["id"],
        rule_name=rule["name"],
        namespace=pod.get("namespace", "default"),
        pod_name=pod.get("pod_name", ""),
        container=pod.get("container", ""),
        resource=resource,
        current_request=current_str,
        recommended_request=recommended_str,
        actual_usage_avg=actual_str,
        action=rule.get("action", "recommend_reduce_request"),
        estimated_savings_pct=savings_pct * (1 - 1 / ratio),  # proportional to overprovisioning
        confidence=confidence,
        reason=(
            f"{resource.upper()} request ({current_str}) is {ratio:.1f}x actual usage ({actual_str}). "
            f"Recommend reducing to {recommended_str} (20-25% headroom above avg)."
        ),
    )
