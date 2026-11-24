"""
Tests for GitHub commit ingestion.

These tests cover the commit-fetching and commit-ingestion functionality
used by Sprint 1 Issue #33, including:

- GitHub commit pagination
- GitHub API error handling
- Project verification
- Repository validation
- Commit-to-project association
- Repository and branch context
- Duplicate-safe synchronization
- Retrieval of stored project commits

No real GitHub API or MongoDB requests are made in these tests.
"""

import requests
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from unittest.mock import patch, MagicMock

from Backend.externalservies.github_commits import (
    _fetch_commits,
    GitHubAuthError,
    GitHubRepoNotFoundError,
    GitHubBranchNotFoundError,
    GitHubAPIError,
)

from Backend.externalservies.commit_service import (
    sync_project_commits,
    get_commits_for_project,
)

from Backend.persistence import upsert_commit

from Backend.externalservies.contributor_service import (
    ProjectNotFoundError,
    ProjectRepoNotConfiguredError,
    RepoMismatchError,
)


# ---------------------------------------------------------------------------
# Shared Test Data
# ---------------------------------------------------------------------------

SAMPLE_PROJECT_ID = str(ObjectId())

SAMPLE_REPO_URL = (
    "https://github.com/test-owner/test-repo"
)

SAMPLE_PROJECT = {
    "_id": SAMPLE_PROJECT_ID,
    "name": "Test Project",
    "ownerId": "507f1f77bcf86cd799439011",
    "members": [{"userId": "507f1f77bcf86cd799439011"}],
    "repo_url": SAMPLE_REPO_URL,
}

SAMPLE_PROJECT_NO_REPO = {
    "_id": SAMPLE_PROJECT_ID,
    "name": "Test Project",
}

SAMPLE_GITHUB_RESULT = {
    "success": True,
    "repository": {
        "owner": "test-owner",
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "url": SAMPLE_REPO_URL,
    },
    "branch": {
        "selected": "develop",
        "default": "main",
        "was_configured": True,
    },
    "commit_count": 2,
    "commits": [
        {
            "sha": "a" * 40,
            "short_sha": "aaaaaaa",
            "author": "Developer One",
            "github_username": "dev1",
            "timestamp": "2026-09-29T10:00:00Z",
            "message": "First test commit",
            "additions": 10,
            "deletions": 2,
            "total_changes": 12,
        },
        {
            "sha": "b" * 40,
            "short_sha": "bbbbbbb",
            "author": "Developer Two",
            "github_username": "dev2",
            "timestamp": "2026-09-29T11:00:00Z",
            "message": "Second test commit",
            "additions": 5,
            "deletions": 1,
            "total_changes": 6,
        },
    ],
}


# ===========================================================================
# GitHub Commit Fetching
# ===========================================================================

class MockResponse:
    """
    Minimal fake requests.Response object used by pagination
    and GitHub API error-handling tests.
    """

    def __init__(
        self,
        json_data=None,
        status_code=200,
        text="",
        headers=None,
    ):
        self._json_data = (
            json_data
            if json_data is not None
            else []
        )
        self.status_code = status_code
        self.text = text
        self.headers = (
            headers
            if headers is not None
            else {}
        )

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._json_data


class MockSession:
    """
    Fake requests.Session that returns responses in sequence
    and records every request made by _fetch_commits.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({
            "url": url,
            "params": params,
            "timeout": timeout,
        })

        if not self.responses:
            raise AssertionError(
                "Unexpected extra GitHub API request."
            )

        return self.responses.pop(0)


def make_commits(start, count):
    """
    Generate simple fake GitHub commit objects.
    """
    return [
        {"sha": f"sha-{number}"}
        for number in range(start, start + count)
    ]


def test_fetch_commits_single_page():
    """
    When fewer than 100 commits are requested, only one API
    request should be necessary.
    """
    session = MockSession([
        MockResponse(make_commits(1, 5)),
    ])

    commits = _fetch_commits(
        session=session,
        owner="test-owner",
        repo="test-repo",
        branch="main",
        max_commits=5,
    )

    assert len(commits) == 5
    assert len(session.calls) == 1

    assert session.calls[0]["params"] == {
        "sha": "main",
        "per_page": 5,
        "page": 1,
    }


def test_fetch_commits_paginates_beyond_100():
    """
    Requesting 150 commits should cause two GitHub API requests.
    """
    first_page = make_commits(1, 100)
    second_page = make_commits(101, 50)

    session = MockSession([
        MockResponse(first_page),
        MockResponse(second_page),
    ])

    commits = _fetch_commits(
        session=session,
        owner="test-owner",
        repo="test-repo",
        branch="main",
        max_commits=150,
    )

    assert len(commits) == 150
    assert len(session.calls) == 2

    assert session.calls[0]["params"] == {
        "sha": "main",
        "per_page": 100,
        "page": 1,
    }

    assert session.calls[1]["params"] == {
        "sha": "main",
        "per_page": 100,
        "page": 2,
    }

    assert commits[0]["sha"] == "sha-1"
    assert commits[99]["sha"] == "sha-100"
    assert commits[100]["sha"] == "sha-101"
    assert commits[-1]["sha"] == "sha-150"


def test_fetch_commits_stops_on_last_page():
    """
    Pagination stops when GitHub returns fewer commits
    than the requested page size.
    """
    first_page = make_commits(1, 68)

    session = MockSession([
        MockResponse(first_page),
    ])

    commits = _fetch_commits(
        session=session,
        owner="test-owner",
        repo="test-repo",
        branch="main",
        max_commits=150,
    )

    assert len(commits) == 68
    assert len(session.calls) == 1

    assert session.calls[0]["params"]["page"] == 1
    assert session.calls[0]["params"]["per_page"] == 100


def test_fetch_commits_handles_authentication_error():
    """
    HTTP 401 should become GitHubAuthError.
    """
    session = MockSession([
        MockResponse(
            status_code=401,
            text="Bad credentials",
        ),
    ])

    try:
        _fetch_commits(
            session=session,
            owner="test-owner",
            repo="test-repo",
            branch="main",
            max_commits=10,
        )
    except GitHubAuthError:
        pass
    else:
        raise AssertionError(
            "Expected GitHubAuthError for HTTP 401."
        )


def test_fetch_commits_handles_missing_branch():
    """
    HTTP 404 should become GitHubBranchNotFoundError.
    """
    session = MockSession([
        MockResponse(
            status_code=404,
            text="Not Found",
        ),
    ])

    try:
        _fetch_commits(
            session=session,
            owner="test-owner",
            repo="test-repo",
            branch="missing-branch",
            max_commits=10,
        )
    except GitHubBranchNotFoundError:
        pass
    else:
        raise AssertionError(
            "Expected GitHubBranchNotFoundError for HTTP 404."
        )


def test_fetch_commits_handles_rate_limit():
    """
    HTTP 403 rate limiting should become GitHubAPIError.
    """
    session = MockSession([
        MockResponse(
             status_code=403,
             text="API rate limit exceeded",
             headers={
                 "X-RateLimit-Remaining": "0",
                 "X-RateLimit-Reset": "1234567890",
             },
        ),
    ])

    try:
        _fetch_commits(
            session=session,
            owner="test-owner",
            repo="test-repo",
            branch="main",
            max_commits=10,
        )
    except GitHubAPIError as exc:
        assert "rate limit" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected GitHubAPIError for rate limiting."
        )


def test_fetch_commits_handles_network_failure():
    """
    requests network failures should become GitHubAPIError.
    """

    class FailingSession:
        def get(self, url, params=None, timeout=None):
            raise requests.exceptions.RequestException(
                "Simulated network failure"
            )

    session = FailingSession()

    try:
        _fetch_commits(
            session=session,
            owner="test-owner",
            repo="test-repo",
            branch="main",
            max_commits=10,
        )
    except GitHubAPIError as exc:
        assert "network failure" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected GitHubAPIError for network failure."
        )



# ===========================================================================
# Commit Ingestion Service
# ===========================================================================

@patch(
    "Backend.externalservies.commit_service.get_project"
)
@patch(
    "Backend.externalservies.commit_service.upsert_commit"
)
@patch(
    "Backend.externalservies.commit_service."
    "get_github_commit_history"
)
def test_sync_project_commits_success(
    mock_get_history,
    mock_upsert,
    mock_get_project,
):
    """
    A valid project should retrieve and persist its GitHub commits.
    """
    mock_get_project.return_value = SAMPLE_PROJECT
    mock_get_history.return_value = SAMPLE_GITHUB_RESULT

    mock_upsert.side_effect = [
        str(ObjectId()),
        str(ObjectId()),
    ]

    result = sync_project_commits(
        project_id=SAMPLE_PROJECT_ID,
        repo_url=SAMPLE_REPO_URL,
        branch="develop",
        max_commits=100,
    )

    assert result["success"] is True
    assert result["project_id"] == SAMPLE_PROJECT_ID
    assert result["synced_count"] == 2
    assert len(result["commits"]) == 2

    mock_get_history.assert_called_once_with(
        repo_url=SAMPLE_REPO_URL,
        branch="develop",
        max_commits=100,
    )

    assert mock_upsert.call_count == 2


@patch(
    "Backend.externalservies.commit_service.get_project"
)
@patch(
    "Backend.externalservies.commit_service.upsert_commit"
)
@patch(
    "Backend.externalservies.commit_service."
    "get_github_commit_history"
)
def test_sync_adds_repository_and_branch_context(
    mock_get_history,
    mock_upsert,
    mock_get_project,
):
    """
    Each commit sent to persistence must contain repository
    and branch information.
    """
    mock_get_project.return_value = SAMPLE_PROJECT
    mock_get_history.return_value = SAMPLE_GITHUB_RESULT
    mock_upsert.return_value = str(ObjectId())

    sync_project_commits(
        project_id=SAMPLE_PROJECT_ID,
        branch="develop",
    )

    assert mock_upsert.call_count == 2

    first_call = mock_upsert.call_args_list[0]

    assert first_call.args[0] == SAMPLE_PROJECT_ID

    stored_commit = first_call.args[1]

    assert stored_commit["repository"] == (
        "test-owner/test-repo"
    )
    assert stored_commit["repository_url"] == (
        SAMPLE_REPO_URL
    )
    assert stored_commit["branch"] == "develop"
    assert stored_commit["default_branch"] == "main"


@patch(
    "Backend.externalservies.commit_service.get_project"
)
@patch(
    "Backend.externalservies.commit_service.upsert_commit"
)
@patch(
    "Backend.externalservies.commit_service."
    "get_github_commit_history"
)
def test_sync_preserves_required_commit_fields(
    mock_get_history,
    mock_upsert,
    mock_get_project,
):
    """
    Required Issue #33 commit fields must survive preparation
    for persistence.
    """
    mock_get_project.return_value = SAMPLE_PROJECT
    mock_get_history.return_value = SAMPLE_GITHUB_RESULT
    mock_upsert.return_value = str(ObjectId())

    sync_project_commits(
        project_id=SAMPLE_PROJECT_ID,
        branch="develop",
    )

    stored_commit = (
        mock_upsert.call_args_list[0].args[1]
    )

    expected = SAMPLE_GITHUB_RESULT["commits"][0]

    assert stored_commit["sha"] == expected["sha"]
    assert stored_commit["author"] == expected["author"]
    assert stored_commit["timestamp"] == expected["timestamp"]
    assert stored_commit["message"] == expected["message"]


@patch(
    "Backend.externalservies.commit_service.get_project"
)
@patch(
    "Backend.externalservies.commit_service.upsert_commit"
)
@patch(
    "Backend.externalservies.commit_service."
    "get_github_commit_history"
)
def test_sync_associates_commit_with_project(
    mock_get_history,
    mock_upsert,
    mock_get_project,
):
    """
    Every upsert must receive the project ID being synchronized.
    """
    mock_get_project.return_value = SAMPLE_PROJECT
    mock_get_history.return_value = SAMPLE_GITHUB_RESULT
    mock_upsert.return_value = str(ObjectId())

    sync_project_commits(SAMPLE_PROJECT_ID)

    for call in mock_upsert.call_args_list:
        assert call.args[0] == SAMPLE_PROJECT_ID


@patch(
    "Backend.externalservies.commit_service.get_project"
)
def test_sync_project_not_found(mock_get_project):
    """
    Synchronization must fail if the project does not exist.
    """
    mock_get_project.return_value = None

    try:
        sync_project_commits(SAMPLE_PROJECT_ID)
    except ProjectNotFoundError:
        pass
    else:
        raise AssertionError(
            "Expected ProjectNotFoundError."
        )


@patch(
    "Backend.externalservies.commit_service.get_project"
)
def test_sync_project_without_repository(
    mock_get_project,
):
    """
    A project with no repository configuration must fail
    when no repo_url is supplied.
    """
    mock_get_project.return_value = SAMPLE_PROJECT_NO_REPO

    try:
        sync_project_commits(SAMPLE_PROJECT_ID)
    except ProjectRepoNotConfiguredError:
        pass
    else:
        raise AssertionError(
            "Expected ProjectRepoNotConfiguredError."
        )


@patch(
    "Backend.externalservies.commit_service.get_project"
)
def test_sync_rejects_repository_mismatch(
    mock_get_project,
):
    """
    A supplied repository must match the project's configured repo.
    """
    mock_get_project.return_value = SAMPLE_PROJECT

    try:
        sync_project_commits(
            SAMPLE_PROJECT_ID,
            repo_url=(
                "https://github.com/"
                "different-owner/different-repo"
            ),
        )
    except RepoMismatchError:
        pass
    else:
        raise AssertionError(
            "Expected RepoMismatchError."
        )


def test_sync_rejects_empty_project_id():
    """
    Empty project IDs must be rejected before database access.
    """
    try:
        sync_project_commits("")
    except ValueError as exc:
        assert "project_id" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for empty project_id."
        )


def test_sync_rejects_invalid_max_commits():
    """
    max_commits must be positive.
    """
    try:
        sync_project_commits(
            SAMPLE_PROJECT_ID,
            max_commits=0,
        )
    except ValueError as exc:
        assert "max_commits" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for invalid max_commits."
        )


@patch(
    "Backend.externalservies.commit_service.get_project"
)
@patch(
    "Backend.externalservies.commit_service.upsert_commit"
)
@patch(
    "Backend.externalservies.commit_service."
    "get_github_commit_history"
)
def test_sync_handles_duplicate_key_defensively(
    mock_get_history,
    mock_upsert,
    mock_get_project,
):
    """
    DuplicateKeyError from a race condition should not crash
    the complete synchronization operation.
    """
    mock_get_project.return_value = SAMPLE_PROJECT
    mock_get_history.return_value = SAMPLE_GITHUB_RESULT

    mock_upsert.side_effect = [
        DuplicateKeyError("duplicate"),
        str(ObjectId()),
    ]

    result = sync_project_commits(
        SAMPLE_PROJECT_ID
    )

    assert result["success"] is True
    assert result["synced_count"] == 1
    assert len(result["commits"]) == 1


@patch(
    "Backend.externalservies.commit_service.get_project"
)
@patch(
    "Backend.externalservies.commit_service."
    "get_github_commit_history"
)
def test_sync_propagates_github_api_error(
    mock_get_history,
    mock_get_project,
):
    """
    GitHub failures must remain visible to the caller.
    """
    mock_get_project.return_value = SAMPLE_PROJECT

    mock_get_history.side_effect = GitHubAPIError(
        "Simulated GitHub failure"
    )

    try:
        sync_project_commits(SAMPLE_PROJECT_ID)
    except GitHubAPIError as exc:
        assert "Simulated GitHub failure" in str(exc)
    else:
        raise AssertionError(
            "Expected GitHubAPIError."
        )


@patch(
    "Backend.externalservies.commit_service."
    "get_project_commits"
)
def test_get_commits_for_project(
    mock_get_project_commits,
):
    """
    Stored project commits should be returned through the service.
    """
    expected = [
        {
            "_id": str(ObjectId()),
            "projectId": SAMPLE_PROJECT_ID,
            "sha": "a" * 40,
        }
    ]

    mock_get_project_commits.return_value = expected

    result = get_commits_for_project(
        SAMPLE_PROJECT_ID
    )

    assert result == expected

    mock_get_project_commits.assert_called_once_with(
        SAMPLE_PROJECT_ID
    )


def test_get_commits_rejects_empty_project_id():
    """
    Empty project IDs should be rejected.
    """
    try:
        get_commits_for_project("")
    except ValueError as exc:
        assert "project_id" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for empty project_id."
        )




# ===========================================================================
# Commit Persistence
# ===========================================================================

@patch("Backend.persistence.commits_collection")
def test_upsert_commit_creates_new_record(mock_collection):
    """
    First upsert should create a new commit record and return its ID.
    """
    new_id = ObjectId()

    mock_collection.update_one.return_value = MagicMock(
        upserted_id=new_id,
        modified_count=0,
    )

    result = upsert_commit(
        SAMPLE_PROJECT_ID,
        SAMPLE_GITHUB_RESULT["commits"][0],
    )

    assert result == str(new_id)
    mock_collection.update_one.assert_called_once()


@patch("Backend.persistence.commits_collection")
def test_upsert_commit_uses_project_and_sha_as_identity(
    mock_collection,
):
    """
    The MongoDB upsert filter must use (projectId, sha).

    This matches the unique compound index and prevents duplicate
    commits within the same project.
    """
    new_id = ObjectId()

    mock_collection.update_one.return_value = MagicMock(
        upserted_id=new_id,
        modified_count=0,
    )

    commit_data = {
        **SAMPLE_GITHUB_RESULT["commits"][0],
        "repository": "test-owner/test-repo",
        "repository_url": SAMPLE_REPO_URL,
        "branch": "develop",
        "default_branch": "main",
    }

    upsert_commit(
        SAMPLE_PROJECT_ID,
        commit_data,
    )

    call_args = mock_collection.update_one.call_args

    filter_arg = call_args.args[0]

    assert filter_arg["projectId"] == ObjectId(
        SAMPLE_PROJECT_ID
    )
    assert filter_arg["sha"] == commit_data["sha"]


@patch("Backend.persistence.commits_collection")
def test_upsert_commit_persists_required_commit_fields(
    mock_collection,
):
    """
    Required Issue #33 commit data must be included in MongoDB's
    update document.
    """
    mock_collection.update_one.return_value = MagicMock(
        upserted_id=ObjectId(),
        modified_count=0,
    )

    commit_data = {
        **SAMPLE_GITHUB_RESULT["commits"][0],
        "repository": "test-owner/test-repo",
        "repository_url": SAMPLE_REPO_URL,
        "branch": "develop",
        "default_branch": "main",
    }

    upsert_commit(
        SAMPLE_PROJECT_ID,
        commit_data,
    )

    call_args = mock_collection.update_one.call_args
    update_doc = call_args.args[1]["$set"]

    assert update_doc["sha"] == commit_data["sha"]
    assert update_doc["author"] == commit_data["author"]
    assert (
        update_doc["timestamp"]
        == commit_data["timestamp"]
    )
    assert update_doc["message"] == commit_data["message"]

    assert (
        update_doc["projectId"]
        == ObjectId(SAMPLE_PROJECT_ID)
    )


@patch("Backend.persistence.commits_collection")
def test_upsert_commit_persists_repository_and_branch_context(
    mock_collection,
):
    """
    Repository and branch context prepared by the commit service
    must actually be stored by the persistence layer.
    """
    mock_collection.update_one.return_value = MagicMock(
        upserted_id=ObjectId(),
        modified_count=0,
    )

    commit_data = {
        **SAMPLE_GITHUB_RESULT["commits"][0],
        "repository": "test-owner/test-repo",
        "repository_url": SAMPLE_REPO_URL,
        "branch": "develop",
        "default_branch": "main",
    }

    upsert_commit(
        SAMPLE_PROJECT_ID,
        commit_data,
    )

    call_args = mock_collection.update_one.call_args
    update_doc = call_args.args[1]["$set"]

    assert (
        update_doc["repository"]
        == "test-owner/test-repo"
    )
    assert (
        update_doc["repository_url"]
        == SAMPLE_REPO_URL
    )
    assert update_doc["branch"] == "develop"
    assert update_doc["default_branch"] == "main"


@patch("Backend.persistence.commits_collection")
def test_upsert_commit_updates_existing_record(
    mock_collection,
):
    """
    If the commit already exists, upsert_commit should return
    the existing document ID rather than create another record.
    """
    existing_id = ObjectId()

    mock_collection.update_one.return_value = MagicMock(
        upserted_id=None,
        modified_count=1,
    )

    commit_data = {
        **SAMPLE_GITHUB_RESULT["commits"][0],
        "repository": "test-owner/test-repo",
        "repository_url": SAMPLE_REPO_URL,
        "branch": "develop",
        "default_branch": "main",
    }

    mock_collection.find_one.return_value = {
        "_id": existing_id,
        "projectId": ObjectId(SAMPLE_PROJECT_ID),
        "sha": commit_data["sha"],
    }

    result = upsert_commit(
        SAMPLE_PROJECT_ID,
        commit_data,
    )

    assert result == str(existing_id)

    mock_collection.find_one.assert_called_once_with({
        "projectId": ObjectId(SAMPLE_PROJECT_ID),
        "sha": commit_data["sha"],
    })


@patch("Backend.persistence.commits_collection")
def test_upsert_commit_uses_mongodb_upsert(mock_collection):
    """
    update_one must use upsert=True so repeated synchronization
    updates an existing (projectId, sha) record.
    """
    mock_collection.update_one.return_value = MagicMock(
        upserted_id=ObjectId(),
        modified_count=0,
    )

    commit_data = {
        **SAMPLE_GITHUB_RESULT["commits"][0],
        "repository": "test-owner/test-repo",
        "repository_url": SAMPLE_REPO_URL,
        "branch": "develop",
        "default_branch": "main",
    }

    upsert_commit(
        SAMPLE_PROJECT_ID,
        commit_data,
    )

    call_args = mock_collection.update_one.call_args

    assert call_args.kwargs["upsert"] is True


@patch("Backend.persistence.commits_collection")
def test_upsert_commit_sets_updated_at(mock_collection):
    """
    Every commit upsert should update the updated_at timestamp.
    """
    from datetime import datetime

    mock_collection.update_one.return_value = MagicMock(
        upserted_id=ObjectId(),
        modified_count=0,
    )

    commit_data = {
        **SAMPLE_GITHUB_RESULT["commits"][0],
        "repository": "test-owner/test-repo",
        "repository_url": SAMPLE_REPO_URL,
        "branch": "develop",
        "default_branch": "main",
    }

    upsert_commit(
        SAMPLE_PROJECT_ID,
        commit_data,
    )

    call_args = mock_collection.update_one.call_args
    update_doc = call_args.args[1]["$set"]

    assert "updated_at" in update_doc
    assert isinstance(update_doc["updated_at"], datetime)


# ===========================================================================
# Commit API
# ===========================================================================

class TestCommitAPI:
    """
    Tests for the FastAPI commit endpoints.

    GitHub and MongoDB operations are mocked so these tests
    do not make real external requests or modify real data.
    """

    def setup_method(self):
        from importlib import import_module
        from unittest.mock import patch

        module = import_module("Backend.routers.data_sync_router")
        self._project_lookup_patch = patch.object(
            module, "get_project", return_value=SAMPLE_PROJECT
        )
        self._project_lookup_patch.start()

    def teardown_method(self):
        patcher = getattr(self, "_project_lookup_patch", None)
        if patcher:
            patcher.stop()

        from Backend.main import app
        from Backend.auth.dependencies import get_current_user
        app.dependency_overrides.pop(get_current_user, None)

    def _get_client(self):
        """
        Create a FastAPI test client for the application.
        """
        from fastapi.testclient import TestClient
        from Backend.main import app
        from Backend.auth.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "_id": "507f1f77bcf86cd799439011",
            "name": "Test Project Manager",
            "email": "test-manager@example.com",
            "role": "project_manager",
        }
        return TestClient(app)

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.get_commits_for_project")
    @patch("Backend.routers.data_sync_router.get_project")
    def test_get_commits_success(
        self,
        mock_get_project,
        mock_get_commits,
        mock_indexes,
    ):
        """
        GET /api/projects/{id}/commits should return the
        project's stored commits.
        """
        mock_get_project.return_value = SAMPLE_PROJECT

        mock_get_commits.return_value = [
            {
                "sha": "a" * 40,
                "author": "Developer One",
                "timestamp": "2026-09-29T10:00:00Z",
                "message": "First test commit",
                "repository": "test-owner/test-repo",
                "branch": "main",
            }
        ]

        with self._get_client() as client:
            response = client.get(
                f"/api/projects/{SAMPLE_PROJECT_ID}/commits"
            )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["sha"] == "a" * 40
        assert data[0]["author"] == "Developer One"
        assert data[0]["repository"] == "test-owner/test-repo"
        assert data[0]["branch"] == "main"

        mock_get_commits.assert_called_once_with(
            SAMPLE_PROJECT_ID
        )

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.get_project")
    def test_get_commits_project_not_found(
        self,
        mock_get_project,
        mock_indexes,
    ):
        """
        GET /commits should return HTTP 404 when the
        project does not exist.
        """
        mock_get_project.return_value = None

        with self._get_client() as client:
            response = client.get(
                f"/api/projects/{SAMPLE_PROJECT_ID}/commits"
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found."

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_success(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        POST /sync-commits should call the commit sync service
        with the values supplied by the API request.
        """
        mock_sync.return_value = {
            "success": True,
            "project_id": SAMPLE_PROJECT_ID,
            "repository": {
                "owner": "test-owner",
                "name": "test-repo",
                "full_name": "test-owner/test-repo",
                "url": SAMPLE_REPO_URL,
            },
            "branch": {
                "selected": "develop",
                "default": "main",
                "was_configured": True,
            },
            "synced_count": 2,
            "commits": SAMPLE_GITHUB_RESULT["commits"],
        }

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={
                    "repo_url": SAMPLE_REPO_URL,
                    "branch": "develop",
                    "max_commits": 150,
                },
            )

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True
        assert data["synced_count"] == 2
        assert data["branch"]["selected"] == "develop"

        mock_sync.assert_called_once_with(
            project_id=SAMPLE_PROJECT_ID,
            repo_url=SAMPLE_REPO_URL,
            branch="develop",
            max_commits=150,
        )

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_uses_default_request_values(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        An empty request body should use:
            repo_url = None
            branch = None
            max_commits = 100
        """
        mock_sync.return_value = {
            "success": True,
            "project_id": SAMPLE_PROJECT_ID,
            "repository": {},
            "branch": {},
            "synced_count": 0,
            "commits": [],
        }

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={},
            )

        assert response.status_code == 200

        mock_sync.assert_called_once_with(
            project_id=SAMPLE_PROJECT_ID,
            repo_url=None,
            branch=None,
            max_commits=100,
        )

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_invalid_max_commits(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        Invalid max_commits values rejected by the service
        should become HTTP 400 responses.
        """
        mock_sync.side_effect = ValueError(
            "max_commits must be greater than 0."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={
                    "max_commits": 0,
                },
            )

        assert response.status_code == 400
        assert "max_commits" in response.json()["detail"]

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_project_not_found(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        ProjectNotFoundError should become HTTP 404.
        """
        mock_sync.side_effect = ProjectNotFoundError(
            "Project not found."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={},
            )

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_repository_not_configured(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        Missing repository configuration should become HTTP 400.
        """
        mock_sync.side_effect = ProjectRepoNotConfiguredError(
            "Project repository is not configured."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={},
            )

        assert response.status_code == 400

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_repository_mismatch(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        A repository that does not match the project's stored
        repository should become HTTP 400.
        """
        mock_sync.side_effect = RepoMismatchError(
            "Repository does not match project configuration."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={
                    "repo_url": (
                        "https://github.com/"
                        "different-owner/different-repo"
                    ),
                },
            )

        assert response.status_code == 400

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_github_auth_error(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        GitHub authentication failure should become HTTP 401.
        """
        mock_sync.side_effect = GitHubAuthError(
            "Invalid GitHub token."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={},
            )

        assert response.status_code == 401

        assert (
            response.json()["detail"]
            == "GitHub authentication failed. "
            "Check the configured token."
        )

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_repository_not_found(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        A missing GitHub repository should become HTTP 404.
        """
        mock_sync.side_effect = GitHubRepoNotFoundError(
            "Repository not found."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={},
            )

        assert response.status_code == 404
        assert "Repository not found" in response.json()["detail"]

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_branch_not_found(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        A missing GitHub branch should become HTTP 404.
        """
        mock_sync.side_effect = GitHubBranchNotFoundError(
            "Branch not found."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={
                    "branch": "missing-branch",
                },
            )

        assert response.status_code == 404
        assert "Branch not found" in response.json()["detail"]

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.routers.data_sync_router.sync_project_commits")
    def test_sync_commits_github_api_error(
        self,
        mock_sync,
        mock_indexes,
    ):
        """
        General GitHub API failures should become HTTP 502.
        """
        mock_sync.side_effect = GitHubAPIError(
            "GitHub API unavailable."
        )

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-commits",
                json={},
            )

        assert response.status_code == 502
        assert "GitHub API unavailable" in response.json()["detail"]