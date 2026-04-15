"""Track verified savings vs estimated savings over time."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DEFAULT_TRACKER_PATH = Path("output/savings_tracker.json")


def load_tracker(path: Path = _DEFAULT_TRACKER_PATH) -> dict:
    """Load existing savings tracker from JSON file, or return empty state."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"entries": [], "summary": {"total_estimated_usd": 0.0, "total_verified_usd": 0.0}}


def record_recommendation(
    tracker: dict,
    recommendation_id: str,
    resource_id: str,
    action: str,
    estimated_savings_usd: float,
    pr_url: str | None = None,
) -> dict:
    """Record a new recommendation in the tracker."""
    entry = {
        "id": recommendation_id,
        "resource_id": resource_id,
        "action": action,
        "status": "pending",  # pending | applied | rejected | verified
        "estimated_savings_usd": round(estimated_savings_usd, 2),
        "verified_savings_usd": None,
        "pr_url": pr_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied_at": None,
        "verified_at": None,
    }
    tracker["entries"].append(entry)
    tracker["summary"]["total_estimated_usd"] = round(
        sum(e["estimated_savings_usd"] for e in tracker["entries"]), 2
    )
    return entry


def mark_applied(tracker: dict, recommendation_id: str) -> bool:
    """Mark a recommendation as applied (change was merged and deployed)."""
    for entry in tracker["entries"]:
        if entry["id"] == recommendation_id:
            entry["status"] = "applied"
            entry["applied_at"] = datetime.now(timezone.utc).isoformat()
            return True
    return False


def verify_savings(
    tracker: dict,
    recommendation_id: str,
    actual_savings_usd: float,
) -> bool:
    """Record verified savings after measuring actual cost reduction."""
    for entry in tracker["entries"]:
        if entry["id"] == recommendation_id:
            entry["status"] = "verified"
            entry["verified_savings_usd"] = round(actual_savings_usd, 2)
            entry["verified_at"] = datetime.now(timezone.utc).isoformat()
            tracker["summary"]["total_verified_usd"] = round(
                sum(e["verified_savings_usd"] or 0 for e in tracker["entries"]), 2
            )
            return True
    return False


def get_accuracy_report(tracker: dict) -> dict[str, Any]:
    """Compute accuracy of savings estimates vs verified actuals."""
    verified = [e for e in tracker["entries"] if e["verified_savings_usd"] is not None]
    if not verified:
        return {"verified_count": 0, "accuracy_pct": None}

    total_estimated = sum(e["estimated_savings_usd"] for e in verified)
    total_verified = sum(e["verified_savings_usd"] for e in verified)
    accuracy = (total_verified / total_estimated * 100) if total_estimated > 0 else 0

    return {
        "verified_count": len(verified),
        "total_estimated_usd": round(total_estimated, 2),
        "total_verified_usd": round(total_verified, 2),
        "accuracy_pct": round(accuracy, 1),
        "variance_usd": round(total_verified - total_estimated, 2),
    }


def save_tracker(tracker: dict, path: Path = _DEFAULT_TRACKER_PATH) -> None:
    """Persist tracker to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tracker, indent=2), encoding="utf-8")
