"""Tests for EC2, K8s, storage rightsizing and savings analyzer."""

import pytest

from finops.recommendations.ec2_rightsizer import analyze_ec2_instances, EC2Recommendation
from finops.recommendations.k8s_rightsizer import analyze_k8s_pods, K8sRecommendation
from finops.recommendations.storage_optimizer import analyze_ebs_volumes, analyze_s3_buckets
from finops.recommendations.savings_analyzer import analyze_savings_opportunities


# ── EC2 rightsizer ────────────────────────────────────────────────────────────

@pytest.fixture
def ec2_low_cpu():
    return {
        "instance_id": "i-0abc123def456",
        "instance_type": "t3.medium",
        "region": "us-east-1",
        "monthly_cost_usd": 72.0,
        "metrics": {
            "CPUUtilization": {"average": 8.5, "max": 42.1},
            "mem_used_percent": {"average": 22.3, "max": 55.0},
        },
    }


@pytest.fixture
def ec2_high_cpu():
    return {
        "instance_id": "i-0ghi789jkl012",
        "instance_type": "m5.xlarge",
        "region": "us-west-2",
        "monthly_cost_usd": 280.0,
        "metrics": {
            "CPUUtilization": {"average": 75.2, "max": 98.0},
            "mem_used_percent": {"average": 68.5, "max": 85.0},
        },
    }


@pytest.fixture
def ec2_idle():
    return {
        "instance_id": "i-idle001",
        "instance_type": "t3.large",
        "region": "us-east-1",
        "monthly_cost_usd": 58.0,
        "metrics": {
            "CPUUtilization": {"average": 1.2, "max": 5.0},
            "mem_used_percent": {"average": 5.0, "max": 8.0},
        },
    }


def test_ec2_low_cpu_triggers_recommendation(ec2_low_cpu):
    recs = analyze_ec2_instances([ec2_low_cpu])
    assert len(recs) == 1
    assert recs[0].action == "recommend_downsize"
    assert recs[0].instance_id == "i-0abc123def456"


def test_ec2_high_cpu_no_recommendation(ec2_high_cpu):
    recs = analyze_ec2_instances([ec2_high_cpu])
    assert len(recs) == 0


def test_ec2_idle_triggers_stop(ec2_idle):
    recs = analyze_ec2_instances([ec2_idle])
    assert len(recs) == 1
    assert recs[0].action == "recommend_stop_or_terminate"


def test_ec2_idle_prioritized_over_downsize(ec2_idle):
    # Idle rule should win over low-cpu rule for same instance
    recs = analyze_ec2_instances([ec2_idle])
    assert recs[0].action == "recommend_stop_or_terminate"


def test_ec2_recommendation_as_dict(ec2_low_cpu):
    recs = analyze_ec2_instances([ec2_low_cpu])
    d = recs[0].as_dict()
    assert "instance_id" in d
    assert "estimated_savings_usd" in d
    assert d["estimated_savings_usd"] > 0


def test_ec2_savings_estimate_positive(ec2_low_cpu):
    recs = analyze_ec2_instances([ec2_low_cpu])
    assert recs[0].estimated_savings_usd > 0
    assert recs[0].estimated_savings_usd < recs[0].monthly_cost_usd


def test_ec2_recommended_type_mapped(ec2_low_cpu):
    recs = analyze_ec2_instances([ec2_low_cpu])
    # t3.medium should recommend t3.small
    assert recs[0].recommended_type == "t3.small"


def test_ec2_sorted_by_savings():
    instances = [
        {
            "instance_id": "i-cheap",
            "instance_type": "t3.small",
            "region": "us-east-1",
            "monthly_cost_usd": 10.0,
            "metrics": {"CPUUtilization": {"average": 5.0, "max": 10.0}},
        },
        {
            "instance_id": "i-expensive",
            "instance_type": "m5.xlarge",
            "region": "us-east-1",
            "monthly_cost_usd": 300.0,
            "metrics": {"CPUUtilization": {"average": 5.0, "max": 10.0},
                        "mem_used_percent": {"average": 5.0, "max": 10.0}},
        },
    ]
    recs = analyze_ec2_instances(instances)
    savings = [r.estimated_savings_usd for r in recs]
    assert savings == sorted(savings, reverse=True)


# ── K8s rightsizer ───────────────────────────────────────────────────────────

@pytest.fixture
def k8s_overprovisioned_cpu():
    return {
        "namespace": "production",
        "pod_name": "api-server-abc123",
        "container": "api",
        "cpu_request_millicores": 1000,
        "cpu_usage_avg_millicores": 150,     # ratio = 6.67x > threshold 3x
        "memory_request_mib": 512,
        "memory_usage_avg_mib": 400,          # ratio = 1.28x < threshold 2.5x
    }


@pytest.fixture
def k8s_well_sized():
    return {
        "namespace": "production",
        "pod_name": "worker-def456",
        "container": "worker",
        "cpu_request_millicores": 500,
        "cpu_usage_avg_millicores": 400,     # ratio = 1.25x < threshold 3x
        "memory_request_mib": 256,
        "memory_usage_avg_mib": 200,          # ratio = 1.28x < threshold 2.5x
    }


def test_k8s_overprovisioned_cpu_detected(k8s_overprovisioned_cpu):
    recs = analyze_k8s_pods([k8s_overprovisioned_cpu])
    cpu_recs = [r for r in recs if r.resource == "cpu"]
    assert len(cpu_recs) == 1
    assert cpu_recs[0].action == "recommend_reduce_request"


def test_k8s_well_sized_no_recommendation(k8s_well_sized):
    recs = analyze_k8s_pods([k8s_well_sized])
    assert len(recs) == 0


def test_k8s_recommendation_has_headroom(k8s_overprovisioned_cpu):
    recs = analyze_k8s_pods([k8s_overprovisioned_cpu])
    cpu_rec = next(r for r in recs if r.resource == "cpu")
    # Recommended should be ~120% of actual usage (150m * 1.2 = 180m)
    assert "180m" in cpu_rec.recommended_request


def test_k8s_recommendation_as_dict(k8s_overprovisioned_cpu):
    recs = analyze_k8s_pods([k8s_overprovisioned_cpu])
    d = recs[0].as_dict()
    assert "namespace" in d
    assert "estimated_savings_pct" in d


# ── Storage optimizer ─────────────────────────────────────────────────────────

@pytest.fixture
def ebs_low_usage():
    return {
        "volume_id": "vol-0abc123",
        "volume_type": "gp2",
        "size_gb": 100,
        "region": "us-east-1",
        "monthly_cost_usd": 10.0,
        "metrics": {
            "VolumeReadOps": {"average": 1.0},
            "VolumeWriteOps": {"average": 2.0},
        },
    }


@pytest.fixture
def ebs_high_usage():
    return {
        "volume_id": "vol-busy",
        "volume_type": "gp3",
        "size_gb": 500,
        "region": "us-east-1",
        "monthly_cost_usd": 50.0,
        "metrics": {
            "VolumeReadOps": {"average": 800.0},
            "VolumeWriteOps": {"average": 600.0},
        },
    }


def test_ebs_low_usage_detected(ebs_low_usage):
    recs = analyze_ebs_volumes([ebs_low_usage])
    assert len(recs) == 1
    assert "gp3" in recs[0].recommended_config or "Delete" in recs[0].recommended_config


def test_ebs_high_usage_no_recommendation(ebs_high_usage):
    recs = analyze_ebs_volumes([ebs_high_usage])
    assert len(recs) == 0


def test_s3_missing_lifecycle():
    bucket = {
        "bucket_name": "my-data-bucket",
        "region": "us-east-1",
        "monthly_cost_usd": 25.0,
        "has_lifecycle_policy": False,
        "size_gb": 500.0,
        "growth_rate_pct": 15.0,
    }
    recs = analyze_s3_buckets([bucket])
    assert len(recs) == 1
    assert recs[0].action == "add_lifecycle_policy"
    assert recs[0].estimated_savings_usd > 0


def test_s3_with_lifecycle_no_recommendation():
    bucket = {
        "bucket_name": "my-data-bucket",
        "region": "us-east-1",
        "monthly_cost_usd": 25.0,
        "has_lifecycle_policy": True,
        "size_gb": 500.0,
        "growth_rate_pct": 5.0,
    }
    recs = analyze_s3_buckets([bucket])
    assert len(recs) == 0


# ── Savings analyzer ─────────────────────────────────────────────────────────

def test_savings_analyzer_returns_list(in_memory_store):
    recs = analyze_savings_opportunities(in_memory_store, "2024-01-15", "2024-01-18",
                                         min_monthly_cost=1.0)
    assert isinstance(recs, list)


def test_savings_analyzer_sorted_by_savings(in_memory_store):
    recs = analyze_savings_opportunities(in_memory_store, "2024-01-15", "2024-01-18",
                                         min_monthly_cost=1.0)
    if len(recs) > 1:
        savings = [r.estimated_monthly_savings_usd for r in recs]
        assert savings == sorted(savings, reverse=True)


def test_savings_analyzer_no_recommendations_high_threshold(in_memory_store):
    # Very high min threshold — no service qualifies
    recs = analyze_savings_opportunities(in_memory_store, "2024-01-15", "2024-01-18",
                                         min_monthly_cost=100_000)
    assert recs == []
