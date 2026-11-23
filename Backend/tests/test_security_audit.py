"""Defensive HTTP checks for MongoDB query inputs and project authorization."""

from unittest.mock import Mock

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from Backend import persistence, persistence_reports
from Backend.auth.security import create_access_token
from Backend.main import app


client = TestClient(app)


@pytest.fixture
def db(monkeypatch):
    db = mongomock.MongoClient().security_audit
    monkeypatch.setattr(persistence, "users_collection", db.users)
    monkeypatch.setattr(persistence, "projects_collection", db.projects)
    monkeypatch.setattr(persistence_reports, "reports_collection", db.reports)
    monkeypatch.setattr(app, "dependency_overrides", {})
    return db


def account(db, role, name):
    user_id = db.users.insert_one({
        "name": name,
        "email": f"{ObjectId()}@example.com",
        "role": role,
    }).inserted_id
    token = create_access_token({"sub": str(user_id), "role": role})
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("route, field", [
    ("login", "email"),
    ("login", "password"),
    ("signup", "email"),
])
def test_auth_rejects_structured_credentials_before_database_lookup(db, monkeypatch, route, field):
    lookup = Mock(wraps=db.users.find_one)
    monkeypatch.setattr(db.users, "find_one", lookup)
    credentials = {"email": "reader@example.com", "password": "test-password"}
    if route == "signup":
        credentials["name"] = "Test Reader"
    credentials[field] = {"value": credentials[field]}

    response = client.post(f"/auth/{route}", json=credentials)

    assert response.status_code == 422
    assert ["body", field] in [error["loc"] for error in response.json()["detail"]]
    lookup.assert_not_called()
    assert db.users.count_documents({}) == 0


def test_admin_search_treats_quotes_and_regex_punctuation_literally(db):
    _, admin = account(db, "admin", "Administrator")
    match_id, _ = account(db, "developer", "O'Brien (v2.1)")
    account(db, "developer", "O'Brien v2x1")
    account(db, "developer", "O'Brien (v2x1)")

    response = client.get("/api/admin/users", headers=admin, params={"search": "O'Brien (v2.1)"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [user["id"] for user in response.json()["items"]] == [str(match_id)]


def test_project_edit_keeps_text_in_a_single_document_update(db, monkeypatch):
    owner_id, headers = account(db, "project_manager", "Project Manager")
    project_id = db.projects.insert_one({"name": "Release", "ownerId": owner_id}).inserted_id
    neighbor = {"name": "Other release", "ownerId": owner_id}
    db.projects.insert_one(neighbor)
    write = Mock(wraps=db.projects.update_one)
    monkeypatch.setattr(db.projects, "update_one", write)
    description = "O'Brien's SQL migration; phase 2 (50%)."

    response = client.patch(
        f"/api/projects/{project_id}", headers=headers, json={"description": description}
    )

    assert response.status_code == 200
    assert response.json()["description"] == description
    write.assert_called_once()
    selector, changes = write.call_args.args
    assert selector == {"_id": project_id}
    assert set(changes) == {"$set"}
    assert changes["$set"]["description"] == description
    assert db.projects.find_one({"_id": neighbor["_id"]}) == neighbor


def test_report_access_is_scoped_to_the_project_and_its_members(db):
    manager_id, manager = account(db, "project_manager", "Manager")
    other_id, _ = account(db, "project_manager", "Other manager")
    project = db.projects.insert_one({"name": "Release", "ownerId": manager_id}).inserted_id
    other_project = db.projects.insert_one({"name": "Design", "ownerId": other_id}).inserted_id
    own_report = db.reports.insert_one({"projectId": project, "summary": "Release"}).inserted_id
    other_report = db.reports.insert_one({"projectId": other_project, "summary": "Design"}).inserted_id

    path = f"/api/projects/{project}/reports"
    listing = client.get(path, headers=manager)
    assert listing.status_code == 200
    assert [item["_id"] for item in listing.json()["reports"]] == [str(own_report)]
    assert listing.json()["total_reports"] == 1
    assert client.get(f"{path}/{other_report}", headers=manager).status_code == 404
    assert client.get(f"{path}/{other_report}/pdf", headers=manager).status_code == 404
    other_path = f"/api/projects/{other_project}/reports"
    assert client.get(other_path, headers=manager).status_code == 403


def test_report_deletion_requires_management_role_even_for_a_member(db):
    manager_id, manager = account(db, "project_manager", "Manager")
    developer_id, developer = account(db, "developer", "Developer")
    project_id = db.projects.insert_one({
        "name": "Release",
        "ownerId": manager_id,
        "members": [{"userId": developer_id, "role": "member"}],
    }).inserted_id
    report = {"projectId": project_id, "summary": "Team report"}
    report_id = db.reports.insert_one(report).inserted_id
    path = f"/api/projects/{project_id}/reports/{report_id}"

    read = client.get(path, headers=developer)
    assert read.status_code == 200
    assert read.json()["report"]["_id"] == str(report_id)
    assert client.delete(path, headers=developer).status_code == 403
    assert db.reports.find_one({"_id": report_id}) == report
    assert client.delete(path, headers=manager).status_code == 200
    assert db.reports.find_one({"_id": report_id}) is None
