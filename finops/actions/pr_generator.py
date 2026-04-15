"""Generate GitHub PRs with Terraform fix suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from finops.reports.markdown_reporter import generate_pr_body


_GITHUB_API = "https://api.github.com"


def build_terraform_changes(
    ec2_recommendations: list[Any],
    storage_recommendations: list[Any],
) -> list[dict]:
    """Convert recommendations into structured Terraform change dicts."""
    changes = []

    for rec in ec2_recommendations:
        if rec.action == "recommend_downsize" and rec.recommended_type:
            changes.append({
                "resource_id": rec.instance_id,
                "resource_type": "aws_instance",
                "action": "downsize",
                "current_value": rec.instance_type,
                "recommended_value": rec.recommended_type,
                "savings_usd": rec.estimated_savings_usd,
                "confidence": rec.confidence,
                "terraform_snippet": (
                    f'resource "aws_instance" "{rec.instance_id}" {{\n'
                    f'  instance_type = "{rec.recommended_type}"  '
                    f'# was: {rec.instance_type}\n}}'
                ),
            })
        elif rec.action == "recommend_stop_or_terminate":
            changes.append({
                "resource_id": rec.instance_id,
                "resource_type": "aws_instance",
                "action": "stop_or_terminate",
                "current_value": rec.instance_type,
                "recommended_value": "stopped",
                "savings_usd": rec.estimated_savings_usd,
                "confidence": rec.confidence,
                "terraform_snippet": (
                    f"# Consider removing {rec.instance_id} ({rec.instance_type}) "
                    f"— CPU avg {f'{rec.cpu_avg_pct:.1f}' if rec.cpu_avg_pct is not None else 'N/A'}%"
                ),
            })

    for rec in storage_recommendations:
        if rec.action == "migrate_to_gp3":
            changes.append({
                "resource_id": rec.resource_id,
                "resource_type": "aws_ebs_volume",
                "action": "migrate_to_gp3",
                "current_value": rec.current_config,
                "recommended_value": rec.recommended_config,
                "savings_usd": rec.estimated_savings_usd,
                "confidence": rec.confidence,
                "terraform_snippet": (
                    f'resource "aws_ebs_volume" "{rec.resource_id}" {{\n'
                    f'  type = "gp3"  # was: gp2 (-20% cost)\n}}'
                ),
            })

    return changes


def create_github_pr(
    token: str,
    owner: str,
    repo: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str = "main",
    dry_run: bool = False,
) -> dict:
    """
    Create a GitHub pull request.

    dry_run=True returns the payload without making the API call.
    """
    payload = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch,
        "draft": True,  # Always draft — human approval required
    }

    if dry_run:
        return {"dry_run": True, "payload": payload}

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.post(
        f"{_GITHUB_API}/repos/{owner}/{repo}/pulls",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def generate_pr(
    ec2_recommendations: list[Any],
    storage_recommendations: list[Any],
    evaluation_period_days: int,
    metrics_source: str,
    github_token: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
    head_branch: str = "finops/rightsizing",
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Full PR generation flow: build changes → render PR body → create PR.

    Returns the GitHub PR response or dry_run payload.
    """
    changes = build_terraform_changes(ec2_recommendations, storage_recommendations)
    if not changes:
        return {"status": "no_changes", "changes": []}

    estimated_savings = sum(c["savings_usd"] for c in changes)
    rules_applied = list({c["resource_type"] for c in changes})

    pr_body = generate_pr_body(
        changes=changes,
        estimated_savings=estimated_savings,
        evaluation_period_days=evaluation_period_days,
        metrics_source=metrics_source,
        rules_applied=rules_applied,
    )

    title = (
        f"finops: rightsizing recommendations — "
        f"${estimated_savings:.0f}/mo estimated savings ({len(changes)} changes)"
    )

    if not github_token or not owner or not repo:
        return {"status": "dry_run", "title": title, "body": pr_body, "changes": changes}

    result = create_github_pr(
        token=github_token,
        owner=owner,
        repo=repo,
        title=title,
        body=pr_body,
        head_branch=head_branch,
        dry_run=dry_run,
    )
    return {"status": "created", "pr": result, "changes": changes}
