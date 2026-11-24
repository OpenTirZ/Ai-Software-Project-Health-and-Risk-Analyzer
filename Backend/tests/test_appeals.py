"""Unit tests for project health flag appeals (database and analysis mocked)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from Backend.auth.dependencies import get_current_user
from Backend.main import app
from Backend.routers.metric_router import get_health_summary_endpoint

client = TestClient(app)
PROJECT_ID = str(ObjectId())
DEVELOPER_ID = str(ObjectId())
MANAGER_ID = str(ObjectId())
OUTSIDER_ID = str(ObjectId())
APPEAL_ID = str(ObjectId())

PROJECT = {
    "_id": PROJECT_ID,
    "name": "Appeals unit-test project",
    "ownerId": str(ObjectId()),
    "members": [
        {"userId": DEVELOPER_ID, "role": "developer"},
        {"userId": MANAGER_ID, "role": "project_manager"},
    ],
    "status": "active",
}
DEVELOPER = {"_id": DEVELOPER_ID, "role": "developer"}
MANAGER = {"_id": MANAGER_ID, "role": "project_manager"}
OUTSIDER = {"_id": OUTSIDER_ID, "role": "developer"}
ADMIN = {"_id": str(ObjectId()), "role": "admin"}
FLAG = {
    "id": "flag_bottleneck_aging_prs",
    "type": "bottleneck",
    "severity": "medium",
    "message": "A pull request is aging.",
    "evidence": {},
}
REASON = "This flag does not reflect the current project situation."


def stored_appeal(status="pending", submitted_by=DEVELOPER_ID, appeal_id=APPEAL_ID):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "_id": appeal_id,
        "projectId": PROJECT_ID,
        "flagId": FLAG["id"],
        "flagType": FLAG["type"],
        "flagMessage": FLAG["message"],
        "reason": REASON,
        "status": status,
        "submittedBy": submitted_by,
        "submittedAt": now,
        "reviewedBy": MANAGER_ID if status != "pending" else None,
        "reviewedAt": now if status != "pending" else None,
        "reviewComment": "Reviewed against project evidence." if status != "pending" else None,
    }


@pytest.fixture(autouse=True)
def reset_auth_override():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def authenticate(user):
    app.dependency_overrides[get_current_user] = lambda: user


def mock_active_flag(monkeypatch):
    monkeypatch.setattr(
        "Backend.routers.appeal_router._fetch_project_data",
        lambda project_id, user: (PROJECT, [], [], [], [], []),
    )
    monkeypatch.setattr(
        "Backend.routers.appeal_router.build_health_summary",
        lambda **kwargs: {"active_flags": [FLAG]},
    )


# POST: submit appeal --------------------------------------------------

def test_developer_can_submit_appeal(monkeypatch):
    authenticate(DEVELOPER)
    mock_active_flag(monkeypatch)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.create_appeal", return_value=APPEAL_ID) as create_mock, \
         patch("Backend.routers.appeal_router.get_appeal", return_value=stored_appeal()):
        response = client.post(
            f"/api/projects/{PROJECT_ID}/appeals",
            json={"flag_id": FLAG["id"], "reason": REASON},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["submitted_by"] == DEVELOPER_ID
    create_mock.assert_called_once()


def test_project_manager_cannot_submit_appeal():
    authenticate(MANAGER)
    response = client.post(f"/api/projects/{PROJECT_ID}/appeals", json={"flag_id": FLAG["id"], "reason": REASON})
    assert response.status_code == 403


def test_admin_cannot_submit_appeal():
    authenticate(ADMIN)
    response = client.post(f"/api/projects/{PROJECT_ID}/appeals", json={"flag_id": FLAG["id"], "reason": REASON})
    assert response.status_code == 403


def test_non_member_developer_cannot_submit_appeal(monkeypatch):
    authenticate(OUTSIDER)
    mock_active_flag(monkeypatch)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT):
        response = client.post(f"/api/projects/{PROJECT_ID}/appeals", json={"flag_id": FLAG["id"], "reason": REASON})
    assert response.status_code == 403


def test_unknown_flag_cannot_be_appealed(monkeypatch):
    authenticate(DEVELOPER)
    monkeypatch.setattr("Backend.routers.appeal_router._fetch_project_data", lambda *args: (PROJECT, [], [], [], [], []))
    monkeypatch.setattr("Backend.routers.appeal_router.build_health_summary", lambda **kwargs: {"active_flags": []})
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.create_appeal") as create_mock:
        response = client.post(f"/api/projects/{PROJECT_ID}/appeals", json={"flag_id": FLAG["id"], "reason": REASON})
    assert response.status_code == 404
    create_mock.assert_not_called()


def test_invalid_appeal_reason_is_rejected():
    authenticate(DEVELOPER)
    response = client.post(f"/api/projects/{PROJECT_ID}/appeals", json={"flag_id": FLAG["id"], "reason": "short"})
    assert response.status_code == 422


def test_invalid_project_id_is_rejected():
    authenticate(DEVELOPER)
    response = client.post("/api/projects/not-an-object-id/appeals", json={"flag_id": FLAG["id"], "reason": REASON})
    assert response.status_code == 400


# GET: list appeals ---------------------------------------------------

def test_developer_sees_only_own_appeals():
    authenticate(DEVELOPER)
    other = stored_appeal(submitted_by=OUTSIDER_ID, appeal_id=str(ObjectId()))
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_project_appeals", return_value=[stored_appeal(), other]):
        response = client.get(f"/api/projects/{PROJECT_ID}/appeals")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["submitted_by"] == DEVELOPER_ID


def test_project_manager_sees_all_project_appeals():
    authenticate(MANAGER)
    items = [stored_appeal(), stored_appeal(submitted_by=OUTSIDER_ID, appeal_id=str(ObjectId()))]
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_project_appeals", return_value=items):
        response = client.get(f"/api/projects/{PROJECT_ID}/appeals")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_non_member_project_manager_cannot_view_appeals():
    authenticate(MANAGER)
    project = {**PROJECT, "members": [{"userId": DEVELOPER_ID, "role": "developer"}]}
    with patch("Backend.routers.appeal_router.get_project", return_value=project):
        response = client.get(f"/api/projects/{PROJECT_ID}/appeals")
    assert response.status_code == 403


def test_admin_cannot_view_appeals():
    authenticate(ADMIN)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT):
        response = client.get(f"/api/projects/{PROJECT_ID}/appeals")
    assert response.status_code == 403


# PATCH: manager review -----------------------------------------------

def test_project_manager_can_approve_appeal():
    authenticate(MANAGER)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_appeal", side_effect=[stored_appeal(), stored_appeal("approved")]), \
         patch("Backend.routers.appeal_router.update_appeal", return_value=True) as update_mock:
        response = client.patch(
            f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}",
            json={"status": "approved", "review_comment": "The flag is no longer relevant."},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert update_mock.call_args.kwargs["expected_status"] == "pending"


def test_project_manager_can_reject_appeal():
    authenticate(MANAGER)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_appeal", side_effect=[stored_appeal(), stored_appeal("rejected")]), \
         patch("Backend.routers.appeal_router.update_appeal", return_value=True):
        response = client.patch(
            f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}",
            json={"status": "rejected", "review_comment": "The original flag is valid."},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_developer_cannot_review_appeal():
    authenticate(DEVELOPER)
    response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "approved", "review_comment": "Reviewed."})
    assert response.status_code == 403


def test_non_member_project_manager_cannot_review_appeal():
    authenticate(MANAGER)
    project = {**PROJECT, "members": [{"userId": DEVELOPER_ID, "role": "developer"}]}
    with patch("Backend.routers.appeal_router.get_project", return_value=project):
        response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "approved", "review_comment": "Reviewed."})
    assert response.status_code == 403


def test_admin_cannot_review_appeal():
    authenticate(ADMIN)
    response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "approved", "review_comment": "Reviewed."})
    assert response.status_code == 403


def test_review_requires_non_empty_comment():
    authenticate(MANAGER)
    response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "approved", "review_comment": "   "})
    assert response.status_code == 422


def test_review_cannot_set_status_to_pending():
    authenticate(MANAGER)
    response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "pending", "review_comment": "Trying to reset."})
    assert response.status_code == 422


def test_already_reviewed_appeal_cannot_be_reviewed_again():
    authenticate(MANAGER)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_appeal", return_value=stored_appeal("approved")), \
         patch("Backend.routers.appeal_router.update_appeal") as update_mock:
        response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "rejected", "review_comment": "Second review."})
    assert response.status_code == 409
    update_mock.assert_not_called()


def test_appeal_from_another_project_cannot_be_reviewed():
    authenticate(MANAGER)
    appeal = stored_appeal()
    appeal["projectId"] = str(ObjectId())
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_appeal", return_value=appeal), \
         patch("Backend.routers.appeal_router.update_appeal") as update_mock:
        response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "approved", "review_comment": "Reviewed."})
    assert response.status_code == 404
    update_mock.assert_not_called()


def test_concurrent_review_conflict_is_returned():
    authenticate(MANAGER)
    with patch("Backend.routers.appeal_router.get_project", return_value=PROJECT), \
         patch("Backend.routers.appeal_router.get_appeal", return_value=stored_appeal()), \
         patch("Backend.routers.appeal_router.update_appeal", return_value=False):
        response = client.patch(f"/api/projects/{PROJECT_ID}/appeals/{APPEAL_ID}", json={"status": "approved", "review_comment": "Reviewed."})
    assert response.status_code == 409


# Health-summary suppression -----------------------------------------

def test_approved_appeal_suppresses_flag_in_health_summary(monkeypatch):
    authenticate(DEVELOPER)
    summary = {
        "project_id": PROJECT_ID,
        "project_name": "Appeals unit-test project",
        "health_score": 80,
        "status": "Good",
        "last_synced_at": None,
        "data_freshness": "fresh",
        "data_availability": {},
        "summary_statement": "Project health is good.",
        "flags_count": {"total": 1, "high": 0, "medium": 1, "low": 0},
        "active_flags": [FLAG],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr("Backend.routers.metric_router._fetch_project_data", lambda *args: (PROJECT, [], [], [], [], []))
    monkeypatch.setattr("Backend.routers.metric_router.build_health_summary", lambda **kwargs: summary.copy())
    monkeypatch.setattr("Backend.routers.metric_router.get_approved_appeal_flag_ids", lambda project_id: {FLAG["id"]})
    result = get_health_summary_endpoint(id=PROJECT_ID, current_user=DEVELOPER)
    assert result["active_flags"] == []
    assert result["flags_count"] == {"total": 0, "high": 0, "medium": 0, "low": 0}


def test_unapproved_appeal_does_not_suppress_flag(monkeypatch):
    summary = {
        "project_id": PROJECT_ID, "project_name": "Appeals unit-test project",
        "health_score": 80, "status": "Good", "last_synced_at": None,
        "data_freshness": "fresh", "data_availability": {},
        "summary_statement": "Project health is good.",
        "flags_count": {"total": 1, "high": 0, "medium": 1, "low": 0},
        "active_flags": [FLAG], "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr("Backend.routers.metric_router._fetch_project_data", lambda *args: (PROJECT, [], [], [], [], []))
    monkeypatch.setattr("Backend.routers.metric_router.build_health_summary", lambda **kwargs: summary.copy())
    monkeypatch.setattr("Backend.routers.metric_router.get_approved_appeal_flag_ids", lambda project_id: set())
    result = get_health_summary_endpoint(id=PROJECT_ID, current_user=DEVELOPER)
    assert result["active_flags"] == [FLAG]
    assert result["flags_count"]["total"] == 1


# Persistence helper unit tests --------------------------------------

def test_update_appeal_uses_expected_status_guard():
    from Backend.persistence import update_appeal
    with patch("Backend.persistence.appeals_collection.update_one", return_value=SimpleNamespace(modified_count=1)) as update_mock:
        result = update_appeal(APPEAL_ID, {"status": "approved"}, expected_status="pending")
    assert result is True
    assert update_mock.call_args.args[0]["status"] == "pending"
    assert update_mock.call_args.args[0]["_id"] == ObjectId(APPEAL_ID)


def test_get_approved_appeal_flag_ids_returns_only_flag_ids():
    from Backend.persistence import get_approved_appeal_flag_ids
    with patch("Backend.persistence.appeals_collection.find", return_value=[{"flagId": "flag_a"}, {"flagId": "flag_b"}]) as find_mock:
        result = get_approved_appeal_flag_ids(PROJECT_ID)
    assert result == {"flag_a", "flag_b"}
    assert find_mock.call_args.args[0]["status"] == "approved"
