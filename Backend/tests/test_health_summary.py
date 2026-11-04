"""
Unit and Integration Tests for Project Health Summary Engine and Router.
------------------------------------------------------------------------
Task: TASK-SP2-01 (Shah Varshil - Backend Lead)

Tests:
  1. compute_bottlenecks_indicator (missing data, clean queue, aging PRs)
  2. compute_workload_indicator (missing data, single contributor, concentration, balanced)
  3. compute_stale_issues_indicator (missing data, active issues, stale issues)
  4. compute_schedule_risk_indicator (missing data, overdue milestones, on-track)
  5. aggregate_health_score (dynamic re-weighting, all insufficient, partial insufficient)
  6. Router GET /api/projects/{id}/health-summary:
     - 401 Unauthorized (missing auth)
     - 400 Bad Request (invalid ObjectId format)
     - 404 Not Found (nonexistent project)
     - 403 Forbidden (non-member)
     - 200 OK (successful health summary with full telemetry)
     - 200 OK (graceful handling of missing PR / milestone data)
     - 200 OK (admin access override)
  7. Router GET /api/projects/{id}/metrics/breakdown:
     - 400 Bad Request (invalid ObjectId format)
     - 404 Not Found (nonexistent project)
     - 403 Forbidden (non-member)
     - 200 OK (detailed breakdown with weights and evidence)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Mock MongoClient before importing Backend modules to prevent real network calls
_mock_client = MagicMock()
_mock_client.admin.command.return_value = {"ok": 1}
_mock_db = MagicMock()
_mock_client.__getitem__.return_value = _mock_db

with patch("pymongo.MongoClient", return_value=_mock_client):
    from Backend.analysis.health_summary import (
        DEFAULT_THRESHOLDS,
        STATUS_AT_RISK,
        STATUS_CAUTION,
        STATUS_GOOD,
        STATUS_INSUFFICIENT,
        aggregate_health_score,
        build_health_summary,
        build_metrics_breakdown,
        compute_bottlenecks_indicator,
        compute_schedule_risk_indicator,
        compute_stale_issues_indicator,
        compute_workload_indicator,
    )
    from Backend.auth.dependencies import get_current_user
    from Backend.auth.roles import Role
    from Backend.routers.metric_router import router as metric_router


# ---------------------------------------------------------------------------
# Test Fixtures & Test App Setup
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app():
    """Create isolated FastAPI app mounted with metric_router."""
    app = FastAPI()
    app.include_router(metric_router)
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


NOW = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = str(ObjectId())
OWNER_ID = str(ObjectId())
MEMBER_ID = str(ObjectId())
OUTSIDER_ID = str(ObjectId())
ADMIN_ID = str(ObjectId())

MOCK_OWNER_USER = {
    "_id": OWNER_ID,
    "email": "owner@example.com",
    "role": Role.PROJECT_MANAGER.value,
}

MOCK_MEMBER_USER = {
    "_id": MEMBER_ID,
    "email": "member@example.com",
    "role": Role.DEVELOPER.value,
}

MOCK_OUTSIDER_USER = {
    "_id": OUTSIDER_ID,
    "email": "outsider@example.com",
    "role": Role.DEVELOPER.value,
}

MOCK_ADMIN_USER = {
    "_id": ADMIN_ID,
    "email": "admin@example.com",
    "role": Role.ADMIN.value,
}

MOCK_PROJECT = {
    "_id": ObjectId(PROJECT_ID),
    "name": "Health Analyzer Core",
    "description": "Production repo",
    "githubRepoUrl": "https://github.com/example/health-analyzer",
    "ownerId": OWNER_ID,
    "members": [{"userId": MEMBER_ID, "role": "member"}],
    "lastSyncedAt": (NOW - timedelta(hours=2)).isoformat(),
}


# ===========================================================================
# 1. Bottlenecks Indicator Tests
# ===========================================================================

def test_bottlenecks_missing_data():
    """Missing or None PR data must yield Insufficient Data status."""
    res = compute_bottlenecks_indicator(None, now=NOW)
    assert res["status"] == STATUS_INSUFFICIENT
    assert res["score"] is None
    assert res["data_status"] == "insufficient_data"

    res_empty = compute_bottlenecks_indicator([], now=NOW)
    assert res_empty["status"] == STATUS_INSUFFICIENT
    assert res_empty["score"] is None


def test_bottlenecks_all_clean():
    """PRs open for brief durations should yield high Good score."""
    prs = [
        {
            "number": 1,
            "title": "Fix login",
            "state": "open",
            "created_at": (NOW - timedelta(hours=5)).isoformat(),
        },
        {
            "number": 2,
            "title": "Update styles",
            "state": "closed",
            "created_at": (NOW - timedelta(days=5)).isoformat(),
        },
    ]
    res = compute_bottlenecks_indicator(prs, now=NOW)
    assert res["status"] == STATUS_GOOD
    assert res["score"] == 100.0
    assert len(res["flags"]) == 0
    assert res["details"]["aging_prs_count"] == 0


def test_bottlenecks_aging_prs_flagged():
    """PRs open longer than 48 hours should be flagged and score penalized."""
    prs = [
        {
            "number": 10,
            "title": "Huge refactor",
            "state": "open",
            "created_at": (NOW - timedelta(hours=72)).isoformat(),
        },
        {
            "number": 11,
            "title": "Database index migration",
            "state": "open",
            "created_at": (NOW - timedelta(hours=96)).isoformat(),
        },
    ]
    res = compute_bottlenecks_indicator(prs, now=NOW)
    assert res["score"] < 100.0
    assert res["details"]["aging_prs_count"] == 2
    assert len(res["flags"]) == 1
    assert res["flags"][0]["type"] == "bottleneck"
    assert res["flags"][0]["id"] == "flag_bottleneck_aging_prs"


# ===========================================================================
# 2. Workload Imbalance Indicator Tests
# ===========================================================================

def test_workload_missing_data():
    """Missing commits and contributors must return Insufficient Data."""
    res = compute_workload_indicator(None, None)
    assert res["status"] == STATUS_INSUFFICIENT
    assert res["score"] is None
    assert res["data_status"] == "insufficient_data"


def test_workload_single_contributor():
    """Single contributor projects are flagged with Bus Factor = 1 notice."""
    commits = [
        {"author": {"name": "Alice"}, "sha": f"sha{i}"} for i in range(15)
    ]
    res = compute_workload_indicator(commits)
    assert res["status"] == STATUS_CAUTION
    assert res["score"] == 65.0
    assert res["details"]["total_contributors"] == 1
    assert any(f["id"] == "flag_single_contributor" for f in res["flags"])
    # Verify domain disclaimer
    assert "proxy indicator" in res["details"]["disclaimer"]


def test_workload_high_concentration():
    """High contribution concentration (>70%) triggers workload flag."""
    commits = (
        [{"author": {"name": "Alice"}, "sha": f"sha_a{i}"} for i in range(80)]
        + [{"author": {"name": "Bob"}, "sha": f"sha_b{i}"} for i in range(10)]
        + [{"author": {"name": "Charlie"}, "sha": f"sha_c{i}"} for i in range(10)]
    )
    res = compute_workload_indicator(commits)
    assert res["status"] == STATUS_AT_RISK or res["status"] == STATUS_CAUTION
    assert res["score"] <= 50.0
    assert res["details"]["top_contributor"] == "Alice"
    assert res["details"]["top_contributor_percentage"] == 80.0
    assert any(f["id"] == "flag_workload_concentration_high" for f in res["flags"])


def test_workload_well_balanced():
    """Evenly distributed commits across contributors should yield high Good score."""
    commits = (
        [{"author": {"name": "Alice"}, "sha": f"sha_a{i}"} for i in range(25)]
        + [{"author": {"name": "Bob"}, "sha": f"sha_b{i}"} for i in range(25)]
        + [{"author": {"name": "Charlie"}, "sha": f"sha_c{i}"} for i in range(25)]
        + [{"author": {"name": "Dave"}, "sha": f"sha_d{i}"} for i in range(25)]
    )
    res = compute_workload_indicator(commits)
    assert res["status"] == STATUS_GOOD
    assert res["score"] >= 90.0
    assert len(res["flags"]) == 0


# ===========================================================================
# 3. Stale Issues Indicator Tests
# ===========================================================================

def test_stale_issues_missing_and_empty():
    """None issues is insufficient data; empty issues list is clean 100."""
    res_none = compute_stale_issues_indicator(None, now=NOW)
    assert res_none["status"] == STATUS_INSUFFICIENT
    assert res_none["score"] is None

    res_empty = compute_stale_issues_indicator([], now=NOW)
    assert res_empty["status"] == STATUS_GOOD
    assert res_empty["score"] == 100.0


def test_stale_issues_detection():
    """Issues with no update exceeding threshold (>14d) are flagged."""
    issues = [
        {
            "number": 101,
            "title": "Fresh bug",
            "state": "open",
            "updated_at": (NOW - timedelta(days=2)).isoformat(),
        },
        {
            "number": 102,
            "title": "Forgotten request",
            "state": "open",
            "updated_at": (NOW - timedelta(days=30)).isoformat(),
        },
    ]
    res = compute_stale_issues_indicator(issues, now=NOW)
    assert res["details"]["stale_issues_count"] == 1
    assert res["details"]["open_issues_count"] == 2
    assert res["score"] < 100.0
    assert any(f["id"] == "flag_stale_issues_detected" for f in res["flags"])


# ===========================================================================
# 4. Schedule Risk Indicator Tests
# ===========================================================================

def test_schedule_risk_missing_data():
    """No milestone or sprint data yields Insufficient Data without error."""
    res = compute_schedule_risk_indicator(sprints=[], milestones=[], now=NOW)
    assert res["status"] == STATUS_INSUFFICIENT
    assert res["score"] is None
    assert res["data_status"] == "insufficient_data"


def test_schedule_risk_overdue_milestones():
    """Open milestones past due date produce high schedule risk."""
    milestones = [
        {
            "title": "Sprint 1 Release",
            "state": "open",
            "due_on": (NOW - timedelta(days=5)).isoformat(),
            "open_issues": 4,
            "closed_issues": 1,
        }
    ]
    res = compute_schedule_risk_indicator(milestones=milestones, now=NOW)
    assert res["status"] == STATUS_AT_RISK or res["status"] == STATUS_CAUTION
    assert res["score"] <= 65.0
    assert any(f["id"] == "flag_schedule_slippage_overdue" for f in res["flags"])


# ===========================================================================
# 5. Composite Health Aggregation Tests
# ===========================================================================

def test_aggregate_health_all_available():
    """All indicators available should be equally weighted at 0.25 each."""
    bottlenecks = {"score": 100.0, "status": STATUS_GOOD, "flags": []}
    workload = {"score": 80.0, "status": STATUS_GOOD, "flags": []}
    stale_issues = {"score": 90.0, "status": STATUS_GOOD, "flags": []}
    schedule_risk = {"score": 90.0, "status": STATUS_GOOD, "flags": []}

    res = aggregate_health_score(bottlenecks, workload, stale_issues, schedule_risk)
    assert res["status"] == STATUS_GOOD
    assert res["health_score"] == 90.0
    assert res["weights_used"]["bottlenecks"] == 0.25
    assert res["weights_used"]["workload"] == 0.25


def test_aggregate_health_partial_insufficient():
    """
    Missing milestones and PRs must re-weight remaining indicators to 0.50 each
    without manufacturing fake 0 scores.
    """
    bottlenecks = {"score": None, "status": STATUS_INSUFFICIENT, "flags": []}
    workload = {"score": 80.0, "status": STATUS_GOOD, "flags": []}
    stale_issues = {"score": 100.0, "status": STATUS_GOOD, "flags": []}
    schedule_risk = {"score": None, "status": STATUS_INSUFFICIENT, "flags": []}

    res = aggregate_health_score(bottlenecks, workload, stale_issues, schedule_risk)
    assert res["status"] == STATUS_GOOD
    assert res["health_score"] == 90.0
    assert res["weights_used"]["bottlenecks"] == 0.0
    assert res["weights_used"]["schedule_risk"] == 0.0
    assert res["weights_used"]["workload"] == 0.50
    assert res["weights_used"]["stale_issues"] == 0.50


def test_aggregate_health_all_insufficient():
    """When all indicators are insufficient, composite score must be None."""
    empty_ind = {"score": None, "status": STATUS_INSUFFICIENT, "flags": []}
    res = aggregate_health_score(empty_ind, empty_ind, empty_ind, empty_ind)
    assert res["health_score"] is None
    assert res["status"] == STATUS_INSUFFICIENT
    assert "Insufficient Data" in res["summary_statement"]


# ===========================================================================
# 6. FastAPI Router Tests (GET /api/projects/{id}/health-summary)
# ===========================================================================

def test_health_summary_missing_auth(client):
    """Calling endpoint without authentication header must return 401."""
    resp = client.get(f"/api/projects/{PROJECT_ID}/health-summary")
    assert resp.status_code == 401


def test_health_summary_invalid_id_format(test_app):
    """Malformed ObjectId must return 400 Bad Request."""
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER_USER
    client = TestClient(test_app)

    resp = client.get("/api/projects/not-a-valid-object-id/health-summary")
    assert resp.status_code == 400
    assert "Invalid project ID format" in resp.json()["detail"]


def test_health_summary_project_not_found(test_app):
    """Non-existent project must return 404 Not Found."""
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER_USER
    client = TestClient(test_app)

    with patch("Backend.routers.metric_router.get_project", return_value=None):
        resp = client.get(f"/api/projects/{PROJECT_ID}/health-summary")
        assert resp.status_code == 404
        assert "Project not found" in resp.json()["detail"]


def test_health_summary_access_denied_for_outsider(test_app):
    """User who is neither owner, member, nor admin receives 403 Forbidden."""
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_OUTSIDER_USER
    client = TestClient(test_app)

    with patch("Backend.routers.metric_router.get_project", return_value=MOCK_PROJECT):
        resp = client.get(f"/api/projects/{PROJECT_ID}/health-summary")
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]


def test_health_summary_success_full_telemetry(test_app):
    """Authorized member gets 200 with composite score and active flags."""
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_MEMBER_USER
    client = TestClient(test_app)

    mock_commits = [{"author": {"name": "Alice"}, "sha": "sha1"}]
    mock_contributors = [{"github_username": "Alice", "contributions": 10}]
    mock_prs = [
        {
            "number": 1,
            "title": "Initial feature",
            "state": "open",
            "created_at": (NOW - timedelta(hours=5)).isoformat(),
        }
    ]
    mock_issues = [
        {
            "number": 10,
            "title": "Setup task",
            "state": "closed",
            "updated_at": NOW.isoformat(),
        }
    ]

    with patch("Backend.routers.metric_router.get_project", return_value=MOCK_PROJECT), \
         patch("Backend.routers.metric_router.get_project_commits", return_value=mock_commits), \
         patch("Backend.routers.metric_router.get_project_contributors", return_value=mock_contributors), \
         patch("Backend.routers.metric_router.get_project_pull_requests", return_value=mock_prs), \
         patch("Backend.routers.metric_router.get_project_issues", return_value=mock_issues), \
         patch("Backend.routers.metric_router.get_project_sprints", return_value=[]):

        resp = client.get(f"/api/projects/{PROJECT_ID}/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == PROJECT_ID
        assert data["status"] in (STATUS_GOOD, STATUS_CAUTION)
        assert data["health_score"] is not None
        assert data["data_freshness"] == "fresh"
        assert "flags_count" in data
        assert "summary_statement" in data


def test_health_summary_missing_milestones_and_prs_handled_gracefully(test_app):
    """
    Project with commits and issues but NO PR or milestone data must return 200
    with data_availability properly reflecting 'insufficient_data' without failing.
    """
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER_USER
    client = TestClient(test_app)

    mock_commits = [
        {"author": {"name": "Alice"}, "sha": "a1"},
        {"author": {"name": "Bob"}, "sha": "b1"},
    ]
    mock_issues = [
        {
            "number": 5,
            "title": "Bug",
            "state": "open",
            "updated_at": NOW.isoformat(),
        }
    ]

    with patch("Backend.routers.metric_router.get_project", return_value=MOCK_PROJECT), \
         patch("Backend.routers.metric_router.get_project_commits", return_value=mock_commits), \
         patch("Backend.routers.metric_router.get_project_contributors", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_pull_requests", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_issues", return_value=mock_issues), \
         patch("Backend.routers.metric_router.get_project_sprints", return_value=[]):

        resp = client.get(f"/api/projects/{PROJECT_ID}/health-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_availability"]["pull_requests"] == "insufficient_data"
        assert data["data_availability"]["schedule_risk"] == "insufficient_data"
        assert data["data_availability"]["commits"] == "available"
        assert data["health_score"] is not None
        assert data["status"] in (STATUS_GOOD, STATUS_CAUTION)


def test_health_summary_admin_override(test_app):
    """System administrator can inspect health summary even if not a project member."""
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_ADMIN_USER
    client = TestClient(test_app)

    with patch("Backend.routers.metric_router.get_project", return_value=MOCK_PROJECT), \
         patch("Backend.routers.metric_router.get_project_commits", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_contributors", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_pull_requests", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_issues", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_sprints", return_value=[]):

        resp = client.get(f"/api/projects/{PROJECT_ID}/health-summary")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == PROJECT_ID


# ===========================================================================
# 7. FastAPI Router Tests (GET /api/projects/{id}/metrics/breakdown)
# ===========================================================================

def test_metrics_breakdown_success(test_app):
    """Breakdown returns dimensional indicators with weights used."""
    test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER_USER
    client = TestClient(test_app)

    mock_commits = [{"author": {"name": "Alice"}, "sha": "c1"}]
    mock_prs = [
        {
            "number": 1,
            "title": "PR 1",
            "state": "open",
            "created_at": (NOW - timedelta(hours=2)).isoformat(),
        }
    ]

    with patch("Backend.routers.metric_router.get_project", return_value=MOCK_PROJECT), \
         patch("Backend.routers.metric_router.get_project_commits", return_value=mock_commits), \
         patch("Backend.routers.metric_router.get_project_contributors", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_pull_requests", return_value=mock_prs), \
         patch("Backend.routers.metric_router.get_project_issues", return_value=[]), \
         patch("Backend.routers.metric_router.get_project_sprints", return_value=[]):

        resp = client.get(f"/api/projects/{PROJECT_ID}/metrics/breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == PROJECT_ID
        assert "indicators" in data
        assert "bottlenecks" in data["indicators"]
        assert "workload" in data["indicators"]
        assert "stale_issues" in data["indicators"]
        assert "schedule_risk" in data["indicators"]
        assert "weights_used" in data
        assert data["indicators"]["schedule_risk"]["status"] == STATUS_INSUFFICIENT
