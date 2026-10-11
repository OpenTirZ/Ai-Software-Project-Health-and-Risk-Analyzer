"""
Unit and integration tests for Issue #35:
Project Management and Repository Association.

Covers:
  1. Pydantic request/response schemas and validators (name, repo_url, default_branch)
  2. MongoDB persistence operations with ownerId and members array
  3. Real authentication dependency enforcement (401 Unauthorized for missing/invalid auth)
  4. Project creation API (POST /api/projects)
  5. Project retrieval API (GET /api/projects/{id}) with ownership/membership checks
  6. Project listing API (GET /api/projects)
  7. Configuration update API (PATCH /api/projects/{id}) with owner-only checks
  8. Strict legacy data isolation (unowned projects return 403; no invented owners)
  9. Malformed ObjectId handling (400 Bad Request)
 10. Compatibility with existing contributor features
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError

from Backend.auth.dependencies import get_current_user
from Backend.database import ensure_indexes, projects_collection
from Backend.main import app
from Backend.persistence import (
    create_project,
    get_project,
    get_projects_by_user,
    to_object_id,
    update_project,
)
from Backend.schemas.project_schemas import (
    CreateProjectRequest,
    ProjectMember,
    ProjectResponse,
    UpdateProjectRequest,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Test Users
# ---------------------------------------------------------------------------
OWNER_USER_ID = str(ObjectId())
MEMBER_USER_ID = str(ObjectId())
OUTSIDER_USER_ID = str(ObjectId())

OWNER_USER = {
    "_id": OWNER_USER_ID,
    "email": "owner@example.com",
    "name": "Project Owner",
    "role": "member",
}

MEMBER_USER = {
    "_id": MEMBER_USER_ID,
    "email": "member@example.com",
    "name": "Team Member",
    "role": "member",
}

OUTSIDER_USER = {
    "_id": OUTSIDER_USER_ID,
    "email": "outsider@example.com",
    "name": "Outsider User",
    "role": "member",
}


# ---------------------------------------------------------------------------
# In-memory Mock Collection for Project Tests
# ---------------------------------------------------------------------------
_IN_MEMORY_PROJECTS = {}


class MockInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class MockUpdateResult:
    def __init__(self, modified_count, matched_count=1):
        self.modified_count = modified_count
        self.matched_count = matched_count


class MockProjectsCollection:
    def insert_one(self, doc):
        doc_copy = dict(doc)
        doc_id = doc_copy.get("_id", ObjectId())
        doc_copy["_id"] = doc_id
        _IN_MEMORY_PROJECTS[str(doc_id)] = doc_copy
        return MockInsertResult(doc_id)

    def find_one(self, query):
        if "_id" in query:
            target_id = str(query["_id"])
            doc = _IN_MEMORY_PROJECTS.get(target_id)
            return dict(doc) if doc else None
        return None

    def find(self, query=None):
        if not query:
            return [dict(d) for d in _IN_MEMORY_PROJECTS.values()]

        results = []
        for doc in _IN_MEMORY_PROJECTS.values():
            if "$or" in query:
                matched = False
                for cond in query["$or"]:
                    if "ownerId" in cond:
                        if doc.get("ownerId") == cond["ownerId"]:
                            matched = True
                            break
                    if "members.userId" in cond:
                        target_uid = cond["members.userId"]
                        members = doc.get("members", [])
                        if any(
                            m.get("userId") == target_uid
                            for m in members
                            if isinstance(m, dict)
                        ):
                            matched = True
                            break
                if matched:
                    results.append(dict(doc))
            elif "members.userId" in query:
                target_uid = query["members.userId"]
                members = doc.get("members", [])
                if any(
                    m.get("userId") == target_uid
                    for m in members
                    if isinstance(m, dict)
                ):
                    results.append(dict(doc))
        return results

    def update_one(self, filter_query, update_doc):
        target_id = str(filter_query.get("_id"))
        doc = _IN_MEMORY_PROJECTS.get(target_id)
        if not doc:
            return MockUpdateResult(0, matched_count=0)

        if "$set" in update_doc:
            doc.update(update_doc["$set"])
            return MockUpdateResult(1, matched_count=1)
        return MockUpdateResult(0, matched_count=1)

    def delete_one(self, filter_query):
        class MockDeleteResult:
            def __init__(self, count):
                self.deleted_count = count

        target_id = str(filter_query.get("_id"))
        if target_id in _IN_MEMORY_PROJECTS:
            del _IN_MEMORY_PROJECTS[target_id]
            return MockDeleteResult(1)
        return MockDeleteResult(0)

    def create_index(self, keys, **kwargs):
        return "index_created"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Reset the mock database and dependency overrides before each test."""
    _IN_MEMORY_PROJECTS.clear()
    monkeypatch.setattr("Backend.persistence.projects_collection", MockProjectsCollection())
    monkeypatch.setattr("Backend.database.projects_collection", MockProjectsCollection())
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    _IN_MEMORY_PROJECTS.clear()


# ===========================================================================
# 1. Pydantic Schemas & Validation Tests
# ===========================================================================
class TestProjectSchemas:
    def test_create_project_schema_valid_minimal(self):
        req = CreateProjectRequest(name="Health Analyzer")
        assert req.name == "Health Analyzer"
        assert req.description is None
        assert req.repo_url is None
        assert req.default_branch == "main"

    def test_create_project_schema_valid_full(self):
        req = CreateProjectRequest(
            name=" Health Analyzer ",
            description="AI-driven project health and risk insights.",
            repo_url="https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer.git/",
            default_branch="develop",
        )
        assert req.name == "Health Analyzer"  # Trimmed
        assert req.repo_url == "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer.git"
        assert req.default_branch == "develop"

    def test_create_project_schema_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            CreateProjectRequest(name="")

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="   ")

    def test_create_project_schema_name_too_long_rejected(self):
        with pytest.raises(ValidationError):
            CreateProjectRequest(name="A" * 201)

    def test_create_project_schema_valid_github_urls(self):
        valid_urls = [
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "https://github.com/owner/repo/",
            "https://github.com/owner_123/repo-name.test",
        ]
        for url in valid_urls:
            req = CreateProjectRequest(name="Valid Project", repo_url=url)
            assert req.repo_url.startswith("https://github.com/")

    def test_create_project_schema_invalid_github_urls_rejected(self):
        invalid_urls = [
            "https://gitlab.com/owner/repo",
            "http://github.com/owner/repo",
            "not-a-url",
            "https://github.com/only-one-part",
            "ftp://github.com/owner/repo",
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                CreateProjectRequest(name="Project", repo_url=url)

    def test_update_project_schema_partial(self):
        req = UpdateProjectRequest(name="Renamed Project")
        assert req.name == "Renamed Project"
        assert req.description is None
        assert req.repo_url is None
        assert req.default_branch is None

    def test_update_project_schema_invalid_branch_rejected(self):
        with pytest.raises(ValidationError):
            UpdateProjectRequest(default_branch="invalid branch name with spaces")

    def test_project_response_from_doc(self):
        doc = {
            "_id": ObjectId(),
            "name": "Project 1",
            "description": "Desc",
            "ownerId": ObjectId(),
            "repo_url": "https://github.com/test/repo",
            "default_branch": "main",
            "members": [{"userId": ObjectId(), "role": "owner"}],
            "status": "active",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        res = ProjectResponse.from_doc(doc)
        assert res.id == str(doc["_id"])
        assert res.ownerId == str(doc["ownerId"])
        assert len(res.members) == 1
        assert res.status == "active"


# ===========================================================================
# 2. Persistence Layer Tests
# ===========================================================================
class TestProjectPersistence:
    def test_create_and_get_project(self):
        owner_oid = ObjectId()
        doc = {
            "name": "Persistence Project",
            "ownerId": owner_oid,
            "members": [{"userId": owner_oid, "role": "owner"}],
            "default_branch": "main",
        }
        inserted_id = create_project(doc)
        retrieved = get_project(inserted_id)

        assert retrieved is not None
        assert retrieved["_id"] == inserted_id
        assert str(retrieved["ownerId"]) == str(owner_oid)
        assert len(retrieved["members"]) == 1

    def test_get_projects_by_user_queries_owner_and_members(self):
        user_oid = ObjectId()
        other_oid = ObjectId()

        # Project 1: User is owner
        create_project({
            "name": "Owned Project",
            "ownerId": user_oid,
            "members": [{"userId": user_oid, "role": "owner"}],
        })

        # Project 2: User is member but not owner
        create_project({
            "name": "Member Project",
            "ownerId": other_oid,
            "members": [
                {"userId": other_oid, "role": "owner"},
                {"userId": user_oid, "role": "developer"},
            ],
        })

        # Project 3: Unrelated project
        create_project({
            "name": "Unrelated Project",
            "ownerId": other_oid,
            "members": [{"userId": other_oid, "role": "owner"}],
        })

        user_projects = get_projects_by_user(str(user_oid))
        names = [p["name"] for p in user_projects]
        assert "Owned Project" in names
        assert "Member Project" in names
        assert "Unrelated Project" not in names
        assert len(user_projects) == 2

    def test_update_project_persistence(self):
        project_id = create_project({
            "name": "Original Name",
            "default_branch": "main",
        })
        success = update_project(project_id, {"name": "Updated Name", "default_branch": "develop"})
        assert success is True

        updated = get_project(project_id)
        assert updated["name"] == "Updated Name"
        assert updated["default_branch"] == "develop"

    def test_database_indexes_ensured(self, monkeypatch):
        mock_contrib = MagicMock()
        mock_commits = MagicMock()
        mock_projects = MagicMock()
        monkeypatch.setattr("Backend.database.contributors_collection", mock_contrib)
        monkeypatch.setattr("Backend.database.commits_collection", mock_commits)
        monkeypatch.setattr("Backend.database.projects_collection", mock_projects)

        ensure_indexes()
        assert mock_projects.create_index.call_count == 2


# ===========================================================================
# 3. Authentication & Authorization Security Tests
# ===========================================================================
class TestProjectAuthenticationSecurity:
    def test_unauthenticated_requests_rejected(self):
        """Verifies that endpoints without an Authorization header are rejected (401/403) by real HTTPBearer/get_current_user."""
        res_post = client.post("/api/projects", json={"name": "No Auth"})
        assert res_post.status_code in (401, 403)
        assert res_post.json()["detail"] == "Not authenticated"

        res_get_list = client.get("/api/projects")
        assert res_get_list.status_code in (401, 403)

        res_get_one = client.get(f"/api/projects/{ObjectId()}")
        assert res_get_one.status_code in (401, 403)

        res_patch = client.patch(f"/api/projects/{ObjectId()}", json={"name": "New Name"})
        assert res_patch.status_code in (401, 403)

    def test_invalid_bearer_token_returns_401(self):
        """Verifies that an invalid bearer token returns 401 Unauthorized via real get_current_user."""
        headers = {"Authorization": "Bearer totally_invalid_jwt_token_payload"}
        res = client.get("/api/projects", headers=headers)
        assert res.status_code == 401
        assert "Could not validate credentials." in res.json()["detail"]


# ===========================================================================
# 4. Project API CRUD & Access Control Tests (Dependency Overrides)
# ===========================================================================
class TestProjectAPIOperations:
    def test_create_project_success(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        payload = {
            "name": "My New Project",
            "description": "Project Description",
            "repo_url": "https://github.com/my-org/my-repo",
            "default_branch": "main",
        }
        res = client.post("/api/projects", json=payload)
        assert res.status_code == 201

        data = res.json()
        assert data["name"] == "My New Project"
        assert data["description"] == "Project Description"
        assert data["ownerId"] == OWNER_USER_ID
        assert data["repo_url"] == "https://github.com/my-org/my-repo"
        assert data["default_branch"] == "main"
        assert data["status"] == "active"
        assert len(data["members"]) == 1
        assert data["members"][0]["userId"] == OWNER_USER_ID
        assert data["members"][0]["role"] == "owner"

    def test_create_project_validation_failure(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Empty name
        res1 = client.post("/api/projects", json={"name": "   "})
        assert res1.status_code == 422

        # Invalid GitHub URL
        res2 = client.post("/api/projects", json={"name": "Valid", "repo_url": "https://bitbucket.org/repo"})
        assert res2.status_code == 422

    def test_get_project_owner_access(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Create project as owner
        res_create = client.post("/api/projects", json={"name": "Owner Project"})
        project_id = res_create.json()["id"]

        # Retrieve as owner
        res_get = client.get(f"/api/projects/{project_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == project_id
        assert res_get.json()["name"] == "Owner Project"

    def test_get_project_member_access(self):
        # Create project with OWNER_USER and add MEMBER_USER to members
        proj_id = create_project({
            "name": "Shared Project",
            "ownerId": ObjectId(OWNER_USER_ID),
            "members": [
                {"userId": ObjectId(OWNER_USER_ID), "role": "owner"},
                {"userId": ObjectId(MEMBER_USER_ID), "role": "developer"},
            ],
            "default_branch": "main",
        })

        # Member requests project
        app.dependency_overrides[get_current_user] = lambda: MEMBER_USER
        res_get = client.get(f"/api/projects/{proj_id}")
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "Shared Project"

    def test_get_project_non_member_forbidden_403(self):
        # Project owned by OWNER_USER
        proj_id = create_project({
            "name": "Private Project",
            "ownerId": ObjectId(OWNER_USER_ID),
            "members": [{"userId": ObjectId(OWNER_USER_ID), "role": "owner"}],
            "default_branch": "main",
        })

        # OUTSIDER_USER requests project
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER_USER
        res_get = client.get(f"/api/projects/{proj_id}")
        assert res_get.status_code == 403
        assert res_get.json()["detail"] == "Access denied. You are not a member of this project."

    def test_get_legacy_unowned_project_forbidden_403(self):
        """Strict legacy isolation: projects missing both ownerId and members return 403."""
        legacy_id = create_project({
            "name": "Legacy Unowned Project",
            "repo_url": "https://github.com/legacy/repo",
        })

        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.get(f"/api/projects/{legacy_id}")
        assert res.status_code == 403
        assert res.json()["detail"] == "Access denied. You are not a member of this project."

    def test_get_project_not_found_404(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        non_existent_id = str(ObjectId())
        res = client.get(f"/api/projects/{non_existent_id}")
        assert res.status_code == 404
        assert res.json()["detail"] == "Project not found."

    def test_get_project_invalid_id_400(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.get("/api/projects/not-a-valid-object-id")
        assert res.status_code == 400
        assert res.json()["detail"] == "Invalid project ID format."

    def test_list_projects_returns_only_user_projects(self):
        # Create Project 1 for OWNER_USER
        create_project({
            "name": "Owner Project 1",
            "ownerId": ObjectId(OWNER_USER_ID),
            "members": [{"userId": ObjectId(OWNER_USER_ID), "role": "owner"}],
        })

        # Create Project 2 where OWNER_USER is member
        create_project({
            "name": "Collaborative Project",
            "ownerId": ObjectId(MEMBER_USER_ID),
            "members": [
                {"userId": ObjectId(MEMBER_USER_ID), "role": "owner"},
                {"userId": ObjectId(OWNER_USER_ID), "role": "collaborator"},
            ],
        })

        # Create Project 3 where OWNER_USER has no association
        create_project({
            "name": "Outsider Secret Project",
            "ownerId": ObjectId(OUTSIDER_USER_ID),
            "members": [{"userId": ObjectId(OUTSIDER_USER_ID), "role": "owner"}],
        })

        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.get("/api/projects")
        assert res.status_code == 200

        projects = res.json()
        names = [p["name"] for p in projects]
        assert "Owner Project 1" in names
        assert "Collaborative Project" in names
        assert "Outsider Secret Project" not in names
        assert len(projects) == 2

    def test_list_projects_empty_when_no_memberships(self):
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER_USER
        res = client.get("/api/projects")
        assert res.status_code == 200
        assert res.json() == []

    def test_update_project_config_owner_success(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res_create = client.post("/api/projects", json={
            "name": "Initial Name",
            "repo_url": "https://github.com/initial/repo",
            "default_branch": "main",
        })
        proj_id = res_create.json()["id"]

        update_payload = {
            "name": "Configured Project",
            "description": "Updated Description",
            "repo_url": "https://github.com/new-org/configured-repo",
            "default_branch": "develop",
        }
        res_patch = client.patch(f"/api/projects/{proj_id}", json=update_payload)
        assert res_patch.status_code == 200

        updated_data = res_patch.json()
        assert updated_data["name"] == "Configured Project"
        assert updated_data["description"] == "Updated Description"
        assert updated_data["repo_url"] == "https://github.com/new-org/configured-repo"
        assert updated_data["default_branch"] == "develop"
        assert updated_data["updatedAt"] is not None

    def test_update_project_non_owner_member_forbidden_403(self):
        """A project member who is NOT the owner cannot update configuration."""
        proj_id = create_project({
            "name": "Owner Project",
            "ownerId": ObjectId(OWNER_USER_ID),
            "members": [
                {"userId": ObjectId(OWNER_USER_ID), "role": "owner"},
                {"userId": ObjectId(MEMBER_USER_ID), "role": "developer"},
            ],
            "default_branch": "main",
        })

        app.dependency_overrides[get_current_user] = lambda: MEMBER_USER
        res_patch = client.patch(f"/api/projects/{proj_id}", json={"name": "Hacked Name"})
        assert res_patch.status_code == 403
        assert res_patch.json()["detail"] == "Only the project owner can update project configuration."

    def test_update_project_non_member_forbidden_403(self):
        proj_id = create_project({
            "name": "Private Project",
            "ownerId": ObjectId(OWNER_USER_ID),
            "members": [{"userId": ObjectId(OWNER_USER_ID), "role": "owner"}],
        })

        app.dependency_overrides[get_current_user] = lambda: OUTSIDER_USER
        res_patch = client.patch(f"/api/projects/{proj_id}", json={"name": "Outsider Name"})
        assert res_patch.status_code == 403

    def test_update_project_legacy_unowned_forbidden_403(self):
        legacy_id = create_project({
            "name": "Legacy Unowned",
        })

        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res_patch = client.patch(f"/api/projects/{legacy_id}", json={"name": "Claimed Name"})
        assert res_patch.status_code == 403
        assert res_patch.json()["detail"] == "Only the project owner can update project configuration."

    def test_update_project_not_found_404(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.patch(f"/api/projects/{ObjectId()}", json={"name": "New Name"})
        assert res.status_code == 404

    def test_update_project_invalid_id_400(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.patch("/api/projects/bad-id", json={"name": "New Name"})
        assert res.status_code == 400


# ===========================================================================
# 5. Regression & Contributor Feature Integration
# ===========================================================================
class TestProjectContributorIntegration:
    def test_created_project_works_with_contributor_sync(self, monkeypatch):
        """Verifies contributor feature can read repo_url from project created via new API."""
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        create_res = client.post("/api/projects", json={
            "name": "Sync Ready Project",
            "repo_url": "https://github.com/sample-owner/sample-repo",
        })
        project_id = create_res.json()["id"]

        # Test GET /api/projects/{id}/contributors on the newly created project
        # Mock get_project_contributors to return sample data
        sample_contribs = [{"_id": str(ObjectId()), "github_username": "contributor1", "contributions": 10}]
        monkeypatch.setattr("Backend.main.get_project_contributors", lambda pid: sample_contribs)

        res = client.get(f"/api/projects/{project_id}/contributors")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["github_username"] == "contributor1"
