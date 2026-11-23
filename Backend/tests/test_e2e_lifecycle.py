"""Exercise the project lifecycle through the mounted FastAPI application."""

import json
from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
from io import BytesIO
from unittest.mock import Mock

import mongomock
import pytest
from fastapi.testclient import TestClient
from mongomock.collection import BulkOperationBuilder
from pypdf import PdfReader

from Backend import database, persistence, persistence_reports, persistence_telemetry
from Backend.auth.security import create_access_token
from Backend.externalservies import github_commits, github_issues, github_prs
from Backend.main import app
from Backend.routers import report_router
from Backend.tests.test_github_issues import make_response


REPO = "https://github.com/acme/widgets"
SHA = "a1b2c3d4" * 5
SUMMARY = "The review queue contains one aging pull request."


@pytest.fixture
def client(monkeypatch):
    db = mongomock.MongoClient().lifecycle
    db.users.create_index(
        [("email_normalized", 1)],
        unique=True,
        name="uniq_users_email_normalized",
    )
    # Each DAO imports collection references. Bind them to the same test DB so
    # later HTTP requests only see records actually written by earlier ones.
    for attr in vars(database):
        if attr.endswith("_collection"):
            collection = db[attr.removesuffix("_collection")]
            for module in (database, persistence, persistence_reports, persistence_telemetry):
                if hasattr(module, attr):
                    monkeypatch.setattr(module, attr, collection)
    # PyMongo 4.18 passes sort=None on every UpdateOne. mongomock 4.3 can
    # execute this unsorted bulk write once the unused argument is omitted.
    add_update = BulkOperationBuilder.add_update

    def add_unsorted_update(bulk, *args, sort=None, **kwargs):
        assert sort is None, "The in-memory database only supports unsorted bulk updates"
        return add_update(bulk, *args, **kwargs)

    monkeypatch.setattr(BulkOperationBuilder, "add_update", add_unsorted_update)
    monkeypatch.setattr(app, "dependency_overrides", {})
    with TestClient(app) as http:
        yield http


@pytest.fixture
def github(monkeypatch):
    then = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    author = {"login": "avery"}
    issue = {
        "id": 1002, "number": 2, "title": "Investigate delayed builds",
        "state": "open", "user": author, "assignees": [author],
        "created_at": then, "updated_at": then,
    }
    pr = {
        "number": 1, "title": "Improve build logging", "state": "open",
        "user": author, "created_at": then, "updated_at": then,
    }
    commit = {
        "sha": SHA, "author": author,
        "commit": {"message": "fix: add build logs", "author": {"name": "Avery", "date": then}},
    }
    api = "https://api.github.com/repos/acme/widgets"
    replies = {
        api: {"default_branch": "main", "html_url": REPO},
        f"{api}/commits": [commit],
        f"{api}/commits/{SHA}": {"stats": {"additions": 4, "deletions": 1, "total": 5}},
        f"{api}/pulls": [pr],
        f"{api}/pulls/1": {"additions": 4, "deletions": 1},
        f"{api}/pulls/1/reviews": [],
        f"{api}/issues": [issue, {**pr, "pull_request": {"url": f"{api}/pulls/1"}}],
    }
    session = Mock()
    session.get.side_effect = lambda url, **kwargs: make_response(body=replies[url])
    for service in (github_commits, github_prs, github_issues):
        monkeypatch.setattr(service, "_get_authenticated_session", lambda: session)


def stub_chat_model(monkeypatch):
    for package in ("langgraph", "langchain_core", "langchain_openai"):
        if find_spec(package) is None:
            pytest.skip(f"The report pipeline requires the optional package {package}")
    pipeline = report_router._load_pipeline_v2()
    model = Mock()
    model.invoke.return_value.content = json.dumps({
        "executive_summary": SUMMARY,
        "contributor_summary": "Contributor data is unavailable.",
        "commit_summary": "One commit was synchronized.",
        "pull_request_summary": "One change awaits review.",
        "issue_summary": "One issue remains open.",
        "sprint_summary": "No milestones were synchronized.",
        "recommendations": ["Review the pending change."],
        "limitations": ["This report covers one repository."],
        "risk_explanations": [],
    })
    monkeypatch.setattr(pipeline, "_build_chat_model", lambda: ("fixture", "test-model", model))
    return model


def response_json(response, expected_status=200):
    assert response.status_code == expected_status, response.text
    return response.json()


def test_registered_owner_syncs_telemetry_generates_pdf_and_archives(client, github, monkeypatch, subtests):
    account = response_json(client.post("/api/auth/signup", json={
        "name": "Avery", "email": "avery@example.com", "password": "local-fixture-password",
    }), 201)
    owner = account["user"]
    assert owner["role"] == "developer"
    client.headers["Authorization"] = f"Bearer {account['access_token']}"

    project = response_json(client.post("/api/projects", json={
        "name": "Build Reliability", "repo_url": REPO,
    }), 201)
    project_id = project["id"]
    path = f"/api/projects/{project_id}"
    assert project["ownerId"] == owner["id"]
    assert project["status"] == "active"

    # Issue sync requires a project manager. A separate administrator grants
    # that role through the application to the newly registered project owner.
    admin_id = persistence.create_user({"name": "Admin", "email": "admin@example.com", "role": "admin"})
    admin_token = create_access_token({"sub": admin_id, "role": "admin"})
    granted = response_json(client.patch(
        f"/api/admin/users/{owner['id']}/role", json={"role": "project_manager"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ))
    assert granted["role"] == "project_manager"

    commits = response_json(client.post(f"{path}/sync-commits", json={}))
    prs = response_json(client.post(f"{path}/sync-prs"))
    issues = response_json(client.post(f"{path}/sync-issues"))
    for sync in (commits, prs, issues):
        assert sync["success"] is True
        assert sync["project_id"] == project_id
    assert commits["synced_count"] == prs["created_count"] == issues["persisted_count"] == 1
    assert issues["pull_requests_skipped"] == 1

    [commit] = response_json(client.get(f"{path}/commits"))
    [pr] = response_json(client.get(f"{path}/prs"))
    [issue] = response_json(client.get(f"{path}/issues"))
    assert (commit["sha"], commit["total_changes"]) == (SHA, 5)
    assert (pr["number"], pr["state"]) == (1, "open")
    assert (issue["github_id"], issue["assignees"]) == (1002, ["avery"])

    health = response_json(client.get(f"{path}/health-summary"))
    assert health["project_id"] == project_id
    # One aging PR (85), one contributor (65), and one stale issue (27)
    # contribute equally because this project has no schedule data.
    assert health["health_score"] == 59.0
    assert health["status"] == "Caution"
    for source in ("commits", "pull_requests", "issues"):
        assert health["data_availability"][source] == "available"
    stale = next(flag for flag in health["active_flags"] if flag["type"] == "stale_issues")
    assert stale["evidence"]["stale_issues"][0]["number"] == issue["number"]

    with subtests.test("AI report generation and PDF export"):
        chat_model = stub_chat_model(monkeypatch)
        generated = response_json(client.post(f"{path}/reports/generate"))
        assert generated["project_id"] == project_id
        assert generated["llm_used"] is True
        chat_model.invoke.assert_called_once()
        report = generated["report"]
        assert report["executive_summary"] == SUMMARY
        assert report["commit_report"]["recent_commits"][0]["sha"] == SHA
        assert report["pull_request_report"]["metrics"]["total_prs"] == 1
        assert report["issue_report"]["metrics"]["total_issues"] == 1

        report_path = f"{path}/reports/{generated['report_id']}"
        saved = response_json(client.get(report_path))["report"]
        assert saved["projectId"] == project_id
        assert saved["summary"] == SUMMARY
        assert saved["metricsSnapshot"]["project_health"] == report["project_health"]
        pdf = client.get(f"{report_path}/pdf")
        assert pdf.status_code == 200, pdf.text
        assert pdf.headers["content-type"] == "application/pdf"
        pages = PdfReader(BytesIO(pdf.content)).pages
        pdf_text = " ".join(" ".join(page.extract_text().split()) for page in pages)
        assert project["name"] in pdf_text
        assert SUMMARY in pdf_text

    with subtests.test("Affected user submits an appeal and reads the reviewer's resolution"):
        pytest.skip("FR-17 is planned. The backend has no appeal submission or resolution API.")

    reports_before_archive = response_json(client.get(f"{path}/reports"))
    archived = response_json(client.post(f"{path}/archive"))
    assert (archived["project_id"], archived["status"]) == (project_id, "archived")
    assert response_json(client.get(path))["status"] == "archived"
    assert response_json(client.get(f"{path}/reports")) == reports_before_archive
    assert response_json(client.get(f"{path}/commits")) == [commit]
    assert client.post(f"{path}/sync-commits", json={}).status_code == 400
