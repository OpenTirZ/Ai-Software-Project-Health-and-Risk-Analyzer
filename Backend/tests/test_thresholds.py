"""
Unit and integration tests for Issue #68:
Threshold Management API.

Covers:
  1. Pydantic request/response schemas and boundary validators (threshold_schemas.py)
  2. GET /api/projects/{id}/thresholds default retrieval and custom threshold retrieval
  3. PUT /api/projects/{id}/thresholds permission enforcement (restricted to owner, admin, lead)
  4. Role rejection (developer / non-member / outsider gets 403 Forbidden)
  5. Input validation error handling (422 Unprocessable Entity for negative or out-of-bounds values)
  6. Malformed project ID validation (400 Bad Request)
  7. Non-existent project handling (404 Not Found)
  8. Unauthenticated request handling (401 Unauthorized)
  9. Database error handling (503 Service Unavailable)
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Set test environment variables before module imports
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-threshold-tests-32-chars")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")

# Mock pymongo.MongoClient before Backend.database initializes and pings
import pymongo
_original_mongo_client = pymongo.MongoClient


def _mock_mongo_factory(*args, **kwargs):
    mock = MagicMock()
    mock.admin.command.return_value = {"ok": 1}
    return mock


pymongo.MongoClient = _mock_mongo_factory

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError

from Backend.auth.dependencies import get_current_user
from Backend.main import app
from Backend.persistence import DatabaseError
from Backend.schemas.threshold_schemas import (
    DEFAULT_BUS_FACTOR_THRESHOLD,
    DEFAULT_STALE_ISSUE_DAYS,
    DEFAULT_STALE_PR_HOURS,
    DEFAULT_WORKLOAD_IMBALANCE_RATIO,
    ThresholdConfig,
    ThresholdsResponse,
    UpdateThresholdsRequest,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Test Users & Project Fixtures
# ---------------------------------------------------------------------------

OWNER_USER_ID = str(ObjectId())
ADMIN_USER_ID = str(ObjectId())
LEAD_USER_ID = str(ObjectId())
DEVELOPER_USER_ID = str(ObjectId())
OUTSIDER_USER_ID = str(ObjectId())

OWNER_USER = {
    "_id": OWNER_USER_ID,
    "email": "owner@example.com",
    "name": "Project Owner",
    "role": "project_manager",
}

ADMIN_USER = {
    "_id": ADMIN_USER_ID,
    "email": "admin@example.com",
    "name": "System Admin",
    "role": "admin",
}

LEAD_USER = {
    "_id": LEAD_USER_ID,
    "email": "lead@example.com",
    "name": "Team Lead",
    "role": "lead",
}

DEVELOPER_USER = {
    "_id": DEVELOPER_USER_ID,
    "email": "dev@example.com",
    "name": "Regular Developer",
    "role": "developer",
}

OUTSIDER_USER = {
    "_id": OUTSIDER_USER_ID,
    "email": "outsider@example.com",
    "name": "Outsider",
    "role": "developer",
}

VALID_PROJECT_ID = str(ObjectId())

BASE_PROJECT_DOC = {
    "_id": ObjectId(VALID_PROJECT_ID),
    "name": "Health Analyzer",
    "ownerId": ObjectId(OWNER_USER_ID),
    "members": [
        {"userId": ObjectId(OWNER_USER_ID), "role": "owner"},
        {"userId": ObjectId(LEAD_USER_ID), "role": "lead"},
        {"userId": ObjectId(DEVELOPER_USER_ID), "role": "member"},
    ],
    "thresholds": None,
    "createdAt": datetime.now(timezone.utc),
    "updatedAt": datetime.now(timezone.utc),
}


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Ensure dependency overrides are cleared after every test."""
    yield
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Pydantic Schema and Bounds Validation Tests
# ===========================================================================

class TestThresholdSchemas:
    """Validate Pydantic bounds and defaults."""

    def test_default_threshold_values(self):
        config = ThresholdConfig()
        assert config.stale_pr_hours == DEFAULT_STALE_PR_HOURS
        assert config.stale_issue_days == DEFAULT_STALE_ISSUE_DAYS
        assert config.workload_imbalance_ratio == DEFAULT_WORKLOAD_IMBALANCE_RATIO
        assert config.bus_factor_threshold == DEFAULT_BUS_FACTOR_THRESHOLD

    def test_valid_custom_threshold_values(self):
        config = ThresholdConfig(
            stale_pr_hours=72,
            stale_issue_days=30,
            workload_imbalance_ratio=2.5,
            bus_factor_threshold=0.5,
        )
        assert config.stale_pr_hours == 72
        assert config.stale_issue_days == 30
        assert config.workload_imbalance_ratio == 2.5
        assert config.bus_factor_threshold == 0.5

    def test_stale_pr_hours_must_be_positive(self):
        with pytest.raises(ValidationError):
            ThresholdConfig(stale_pr_hours=0)

        with pytest.raises(ValidationError):
            ThresholdConfig(stale_pr_hours=-10)

    def test_stale_pr_hours_upper_bound(self):
        # 720 hours = 30 days maximum
        assert ThresholdConfig(stale_pr_hours=720).stale_pr_hours == 720
        with pytest.raises(ValidationError):
            ThresholdConfig(stale_pr_hours=721)

    def test_stale_issue_days_must_be_positive(self):
        with pytest.raises(ValidationError):
            ThresholdConfig(stale_issue_days=0)

        with pytest.raises(ValidationError):
            ThresholdConfig(stale_issue_days=-5)

    def test_stale_issue_days_upper_bound(self):
        assert ThresholdConfig(stale_issue_days=365).stale_issue_days == 365
        with pytest.raises(ValidationError):
            ThresholdConfig(stale_issue_days=366)

    def test_workload_imbalance_ratio_bounds(self):
        with pytest.raises(ValidationError):
            ThresholdConfig(workload_imbalance_ratio=1.0)  # Must be strictly > 1.0

        with pytest.raises(ValidationError):
            ThresholdConfig(workload_imbalance_ratio=0.5)

        with pytest.raises(ValidationError):
            ThresholdConfig(workload_imbalance_ratio=25.0)  # Cannot exceed 20.0

        assert ThresholdConfig(workload_imbalance_ratio=1.5).workload_imbalance_ratio == 1.5
        assert ThresholdConfig(workload_imbalance_ratio=20.0).workload_imbalance_ratio == 20.0

    def test_bus_factor_threshold_bounds(self):
        with pytest.raises(ValidationError):
            ThresholdConfig(bus_factor_threshold=0.0)

        with pytest.raises(ValidationError):
            ThresholdConfig(bus_factor_threshold=1.5)

        assert ThresholdConfig(bus_factor_threshold=0.75).bus_factor_threshold == 0.75

    def test_update_request_accepts_partial_fields(self):
        update = UpdateThresholdsRequest(stale_pr_hours=36)
        assert update.stale_pr_hours == 36
        assert update.stale_issue_days is None
        assert update.workload_imbalance_ratio is None

    def test_update_request_validates_negative_values(self):
        with pytest.raises(ValidationError):
            UpdateThresholdsRequest(stale_pr_hours=-1)

        with pytest.raises(ValidationError):
            UpdateThresholdsRequest(stale_issue_days=-1)

        with pytest.raises(ValidationError):
            UpdateThresholdsRequest(workload_imbalance_ratio=0.9)


# ===========================================================================
# 2. GET /api/projects/{id}/thresholds Tests
# ===========================================================================

class TestGetProjectThresholds:
    """Tests for retrieving project health and risk thresholds."""

    def test_unauthenticated_request_rejected(self):
        response = client.get(f"/api/projects/{VALID_PROJECT_ID}/thresholds")
        assert response.status_code == 401

    def test_malformed_project_id_returns_400(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        response = client.get("/api/projects/not-a-valid-id/thresholds")
        assert response.status_code == 400
        assert "Invalid project ID format" in response.json()["detail"]

    @patch("Backend.routers.threshold_router.get_project", return_value=None)
    def test_nonexistent_project_returns_404(self, mock_get_project):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        response = client.get(f"/api/projects/{VALID_PROJECT_ID}/thresholds")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found."

    @patch("Backend.routers.threshold_router.get_project")
    def test_outsider_denied_read_access_403(self, mock_get_project):
        mock_get_project.return_value = BASE_PROJECT_DOC
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER_USER

        response = client.get(f"/api/projects/{VALID_PROJECT_ID}/thresholds")
        assert response.status_code == 403
        assert "not a member" in response.json()["detail"]

    @patch("Backend.routers.threshold_router.get_project")
    def test_retrieves_default_thresholds_when_not_customized(self, mock_get_project):
        mock_get_project.return_value = BASE_PROJECT_DOC
        app.dependency_overrides[get_current_user] = lambda: DEVELOPER_USER

        response = client.get(f"/api/projects/{VALID_PROJECT_ID}/thresholds")
        assert response.status_code == 200

        data = response.json()
        assert data["project_id"] == VALID_PROJECT_ID
        assert data["is_customized"] is False
        assert data["thresholds"]["stale_pr_hours"] == 48
        assert data["thresholds"]["stale_issue_days"] == 14
        assert data["thresholds"]["workload_imbalance_ratio"] == 3.0
        assert data["thresholds"]["bus_factor_threshold"] == 0.60

    @patch("Backend.routers.threshold_router.get_project")
    def test_retrieves_custom_thresholds_when_configured(self, mock_get_project):
        custom_doc = dict(BASE_PROJECT_DOC)
        custom_doc["thresholds"] = {
            "stale_pr_hours": 72,
            "stale_issue_days": 21,
            "workload_imbalance_ratio": 2.5,
            "bus_factor_threshold": 0.55,
        }
        mock_get_project.return_value = custom_doc
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        response = client.get(f"/api/projects/{VALID_PROJECT_ID}/thresholds")
        assert response.status_code == 200

        data = response.json()
        assert data["is_customized"] is True
        assert data["thresholds"]["stale_pr_hours"] == 72
        assert data["thresholds"]["stale_issue_days"] == 21
        assert data["thresholds"]["workload_imbalance_ratio"] == 2.5
        assert data["thresholds"]["bus_factor_threshold"] == 0.55

    @patch("Backend.routers.threshold_router.get_project", side_effect=DatabaseError("DB Down"))
    def test_database_error_returns_503(self, mock_get_project):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        response = client.get(f"/api/projects/{VALID_PROJECT_ID}/thresholds")
        assert response.status_code == 503


# ===========================================================================
# 3. PUT /api/projects/{id}/thresholds Tests
# ===========================================================================

class TestUpdateProjectThresholds:
    """Tests for updating project health and risk thresholds."""

    def test_unauthenticated_request_rejected(self):
        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"stale_pr_hours": 60},
        )
        assert response.status_code == 401

    def test_malformed_project_id_returns_400(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        response = client.put(
            "/api/projects/invalid-object-id/thresholds",
            json={"stale_pr_hours": 60},
        )
        assert response.status_code == 400
        assert "Invalid project ID format" in response.json()["detail"]

    @patch("Backend.routers.threshold_router.get_project", return_value=None)
    def test_nonexistent_project_returns_404(self, mock_get_project):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"stale_pr_hours": 60},
        )
        assert response.status_code == 404

    @patch("Backend.routers.threshold_router.get_project")
    def test_developer_role_forbidden_from_updating_403(self, mock_get_project):
        mock_get_project.return_value = BASE_PROJECT_DOC
        app.dependency_overrides[get_current_user] = lambda: DEVELOPER_USER

        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"stale_pr_hours": 60},
        )
        assert response.status_code == 403
        assert "Only project owners, admins, or leads can update thresholds" in response.json()["detail"]

    @patch("Backend.routers.threshold_router.update_project")
    @patch("Backend.routers.threshold_router.get_project")
    def test_project_owner_successfully_updates_thresholds(
        self, mock_get_project, mock_update_project
    ):
        mock_get_project.return_value = BASE_PROJECT_DOC
        mock_update_project.return_value = True
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        payload = {
            "stale_pr_hours": 36,
            "stale_issue_days": 10,
            "workload_imbalance_ratio": 2.2,
            "bus_factor_threshold": 0.50,
        }
        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json=payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["is_customized"] is True
        assert data["thresholds"]["stale_pr_hours"] == 36
        assert data["thresholds"]["stale_issue_days"] == 10
        assert data["thresholds"]["workload_imbalance_ratio"] == 2.2
        assert data["thresholds"]["bus_factor_threshold"] == 0.50
        assert mock_update_project.called

    @patch("Backend.routers.threshold_router.update_project")
    @patch("Backend.routers.threshold_router.get_project")
    def test_admin_user_successfully_updates_thresholds(
        self, mock_get_project, mock_update_project
    ):
        mock_get_project.return_value = BASE_PROJECT_DOC
        mock_update_project.return_value = True
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"stale_pr_hours": 96},
        )
        assert response.status_code == 200
        assert response.json()["thresholds"]["stale_pr_hours"] == 96

    @patch("Backend.routers.threshold_router.update_project")
    @patch("Backend.routers.threshold_router.get_project")
    def test_lead_user_successfully_updates_thresholds(
        self, mock_get_project, mock_update_project
    ):
        mock_get_project.return_value = BASE_PROJECT_DOC
        mock_update_project.return_value = True
        app.dependency_overrides[get_current_user] = lambda: LEAD_USER

        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"workload_imbalance_ratio": 4.5},
        )
        assert response.status_code == 200
        assert response.json()["thresholds"]["workload_imbalance_ratio"] == 4.5

    @patch("Backend.routers.threshold_router.get_project")
    def test_validation_error_on_negative_stale_pr_hours(self, mock_get_project):
        mock_get_project.return_value = BASE_PROJECT_DOC
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"stale_pr_hours": -5},
        )
        assert response.status_code == 422
        error_detail = response.json().get("detail", [])
        assert any("stale_pr_hours" in str(err.get("loc", [])) for err in error_detail)

    @patch("Backend.routers.threshold_router.get_project")
    def test_validation_error_on_invalid_workload_ratio(self, mock_get_project):
        mock_get_project.return_value = BASE_PROJECT_DOC
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"workload_imbalance_ratio": 0.8},
        )
        assert response.status_code == 422
        error_detail = response.json().get("detail", [])
        assert any("workload_imbalance_ratio" in str(err.get("loc", [])) for err in error_detail)

    @patch("Backend.routers.threshold_router.update_project", side_effect=DatabaseError("DB Failure"))
    @patch("Backend.routers.threshold_router.get_project")
    def test_database_error_on_update_returns_503(
        self, mock_get_project, mock_update_project
    ):
        mock_get_project.return_value = BASE_PROJECT_DOC
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        response = client.put(
            f"/api/projects/{VALID_PROJECT_ID}/thresholds",
            json={"stale_pr_hours": 60},
        )
        assert response.status_code == 503
