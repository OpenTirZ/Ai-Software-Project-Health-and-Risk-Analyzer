"""
Unit and Integration Tests for Repository Router.
------------------------------------------------
Endpoints:
  - POST /api/repositories/connect
  - GET  /api/repositories
  - GET  /api/repositories/branches
"""

from unittest.mock import MagicMock, patch
import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Mock MongoClient before importing Backend modules
_mock_client = MagicMock()
_mock_client.admin.command.return_value = {"ok": 1}
_mock_db = MagicMock()
_mock_client.__getitem__.return_value = _mock_db

with patch("pymongo.MongoClient", return_value=_mock_client):
    from Backend.auth.dependencies import get_current_user
    from Backend.routers.repository_router import router as repository_router


@pytest.fixture
def repo_test_app():
    app = FastAPI()
    app.include_router(repository_router)
    return app


OWNER_ID = str(ObjectId())
OUTSIDER_ID = str(ObjectId())
PROJECT_ID = str(ObjectId())

MOCK_OWNER = {
    "_id": OWNER_ID,
    "email": "owner@example.com",
    "role": "project_manager",
}

MOCK_OUTSIDER = {
    "_id": OUTSIDER_ID,
    "email": "outsider@example.com",
    "role": "developer",
}

MOCK_PROJECT = {
    "_id": ObjectId(PROJECT_ID),
    "name": "Core Service",
    "ownerId": OWNER_ID,
    "members": [{"userId": OWNER_ID, "role": "owner"}],
    "default_branch": "main",
}


def test_connect_repository_invalid_url(repo_test_app):
    repo_test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER
    client = TestClient(repo_test_app)

    resp = client.post(
        "/api/repositories/connect",
        json={"projectId": PROJECT_ID, "githubUrl": "not-a-valid-url", "branch": "main"},
    )
    assert resp.status_code == 400
    assert "Invalid GitHub repository URL format" in resp.json()["detail"]


def test_connect_repository_project_not_found(repo_test_app):
    repo_test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER
    client = TestClient(repo_test_app)

    with patch("Backend.routers.repository_router.get_project", return_value=None):
        resp = client.post(
            "/api/repositories/connect",
            json={
                "projectId": PROJECT_ID,
                "githubUrl": "https://github.com/owner/repo",
                "branch": "main",
            },
        )
        assert resp.status_code == 404
        assert "Project not found" in resp.json()["detail"]


def test_connect_repository_forbidden_for_outsider(repo_test_app):
    repo_test_app.dependency_overrides[get_current_user] = lambda: MOCK_OUTSIDER
    client = TestClient(repo_test_app)

    with patch("Backend.routers.repository_router.get_project", return_value=MOCK_PROJECT):
        resp = client.post(
            "/api/repositories/connect",
            json={
                "projectId": PROJECT_ID,
                "githubUrl": "https://github.com/owner/repo",
                "branch": "main",
            },
        )
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]


def test_connect_repository_success(repo_test_app):
    repo_test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER
    client = TestClient(repo_test_app)

    with patch("Backend.routers.repository_router.get_project", return_value=MOCK_PROJECT), \
         patch("Backend.routers.repository_router.update_project") as mock_update:
        resp = client.post(
            "/api/repositories/connect",
            json={
                "projectId": PROJECT_ID,
                "githubUrl": "https://github.com/aegis/core-api",
                "branch": "develop",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repoName"] == "core-api"
        assert data["githubUrl"] == "https://github.com/aegis/core-api"
        assert data["branch"] == "develop"
        assert data["status"] == "connected"
        mock_update.assert_called_once()


def test_list_repositories(repo_test_app):
    repo_test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER
    client = TestClient(repo_test_app)

    mock_projects = [
        {
            "_id": ObjectId(),
            "name": "Project 1",
            "repo_url": "https://github.com/org/repo1",
            "default_branch": "main",
        },
        {
            "_id": ObjectId(),
            "name": "Project 2 Without Repo",
            "repo_url": None,
        },
    ]

    with patch("Backend.routers.repository_router.get_projects_by_user", return_value=mock_projects):
        resp = client.get("/api/repositories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["repoName"] == "repo1"


def test_fetch_branches_default(repo_test_app):
    repo_test_app.dependency_overrides[get_current_user] = lambda: MOCK_OWNER
    client = TestClient(repo_test_app)

    resp = client.get("/api/repositories/branches?url=https://github.com/invalid-url")
    assert resp.status_code == 200
    data = resp.json()
    assert "main" in data["branches"]
    assert data["source"] == "default"
