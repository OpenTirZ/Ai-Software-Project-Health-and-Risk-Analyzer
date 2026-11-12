"""
Test Suite — GitHub Pull Request Synchronization (Issue #70, TASK-SP2-06)
=========================================================================

Tests:
    - PR normalization (state detection, timestamps, reviewer extraction)
    - Open duration calculation
    - GitHub API error handling (401, 403, 404, 429, rate limit, timeout)
    - Pagination
    - Sync workflow (fetch + persist)
    - GET endpoint (read from DB)
    - POST endpoint (sync from GitHub)
    - Edge cases (empty repos, malformed data, boundary values)
    - Deduplication
    - Authorization (role-based access)
    - Security (no secrets leak)

All tests use mocking — NO real GitHub or MongoDB calls.

Author: Prince Savaliya
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Environment setup — must happen BEFORE importing Backend modules
# ---------------------------------------------------------------------------
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_pr_db")
os.environ.setdefault("MONGO_DATABASE", "test_pr_db")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test_token_for_testing_only")


# ---------------------------------------------------------------------------
# Mock MongoDB at module level to prevent real connection
# ---------------------------------------------------------------------------
_mock_collection = MagicMock()
_mock_db = MagicMock()
_mock_db.__getitem__ = MagicMock(return_value=_mock_collection)

_mock_client_instance = MagicMock()
_mock_client_instance.__getitem__ = MagicMock(return_value=_mock_db)
_mock_client_instance.admin.command = MagicMock(return_value={"ok": 1})

_original_MongoClient = None


def _mock_mongo_client(*args, **kwargs):
    return _mock_client_instance


# Patch pymongo.MongoClient before importing Backend
import pymongo
_original_MongoClient = pymongo.MongoClient
pymongo.MongoClient = _mock_mongo_client

try:
    from Backend.externalservies.github_prs import (
        GitHubPermissionError,
        GitHubRateLimitError,
        _calculate_open_duration_hours,
        _determine_pr_state,
        _extract_requested_reviewers,
        _fetch_all_pr_items,
        _normalize_pr,
        _normalize_timestamp,
        _raise_for_pr_response,
        get_github_prs,
        get_prs_for_project,
        sync_project_prs,
    )
    from Backend.externalservies.github_commits import (
        GitHubAPIError,
        GitHubAuthError,
        GitHubRepoNotFoundError,
        GitHubTokenMissingError,
    )
    from Backend.persistence import DatabaseError
    from Backend.externalservies.contributor_service import ProjectNotFoundError
    from Backend.main import app

    from fastapi.testclient import TestClient
finally:
    # Restore original MongoClient after imports
    pymongo.MongoClient = _original_MongoClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    """FastAPI test client with mocked authentication."""
    client = TestClient(app, raise_server_exceptions=False)
    return client


@pytest.fixture
def mock_user():
    """A standard authenticated user for tests."""
    return {
        "_id": "507f1f77bcf86cd799439011",
        "email": "test@example.com",
        "name": "Test User",
        "role": "admin",
    }


@pytest.fixture
def mock_project():
    """A project document as it would exist in MongoDB."""
    return {
        "_id": "507f1f77bcf86cd799439022",
        "name": "Test Project",
        "repo_url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
        "ownerId": "507f1f77bcf86cd799439011",
        "members": [
            {"userId": "507f1f77bcf86cd799439011", "role": "admin"},
        ],
    }


@pytest.fixture
def sample_raw_pr():
    """A raw PR item as returned by the GitHub API."""
    return {
        "number": 42,
        "title": "feat: add new feature",
        "state": "open",
        "user": {"login": "testuser"},
        "created_at": "2026-01-15T10:30:00Z",
        "updated_at": "2026-01-16T14:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "requested_reviewers": [
            {"login": "reviewer1"},
            {"login": "reviewer2"},
        ],
        "html_url": "https://github.com/test/repo/pull/42",
    }


@pytest.fixture
def sample_repository():
    """Repository metadata dict."""
    return {
        "owner": "OpenTirZ",
        "name": "Ai-Software-Project-Health-and-Risk-Analyzer",
        "full_name": "OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
        "url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
    }


@pytest.fixture
def sample_details():
    """PR details from the individual PR endpoint."""
    return {
        "additions": 150,
        "deletions": 30,
        "reviews_count": 2,
    }


# ---------------------------------------------------------------------------
# 1. Timestamp Normalization Tests
# ---------------------------------------------------------------------------

class TestNormalizeTimestamp:
    def test_valid_utc_timestamp(self):
        result = _normalize_timestamp("2026-01-15T10:30:00Z", "created_at")
        assert result is not None
        assert "+00:00" in result

    def test_valid_offset_timestamp(self):
        result = _normalize_timestamp("2026-01-15T10:30:00+05:30", "created_at")
        assert result is not None
        assert "+00:00" in result

    def test_none_returns_none(self):
        assert _normalize_timestamp(None, "closed_at") is None

    def test_empty_string_returns_none(self):
        assert _normalize_timestamp("", "merged_at") is None

    def test_invalid_type_raises(self):
        with pytest.raises(GitHubAPIError, match="invalid"):
            _normalize_timestamp(12345, "created_at")

    def test_invalid_format_raises(self):
        with pytest.raises(GitHubAPIError, match="invalid"):
            _normalize_timestamp("not-a-date", "created_at")


# ---------------------------------------------------------------------------
# 2. PR State Detection Tests
# ---------------------------------------------------------------------------

class TestDeterminePRState:
    def test_open_pr(self):
        assert _determine_pr_state({"state": "open", "merged_at": None}) == "open"

    def test_closed_pr_not_merged(self):
        assert _determine_pr_state({"state": "closed", "merged_at": None}) == "closed"

    def test_merged_pr(self):
        assert _determine_pr_state({
            "state": "closed",
            "merged_at": "2026-01-15T10:30:00Z",
        }) == "merged"

    def test_missing_state_defaults_to_open(self):
        assert _determine_pr_state({"merged_at": None}) == "open"

    def test_merged_at_overrides_state(self):
        """Even if state says 'open', merged_at wins."""
        assert _determine_pr_state({
            "state": "open",
            "merged_at": "2026-01-15T10:30:00Z",
        }) == "merged"


# ---------------------------------------------------------------------------
# 3. Requested Reviewers Extraction Tests
# ---------------------------------------------------------------------------

class TestExtractRequestedReviewers:
    def test_normal_reviewers(self):
        item = {"requested_reviewers": [{"login": "alice"}, {"login": "bob"}]}
        assert _extract_requested_reviewers(item) == ["alice", "bob"]

    def test_empty_reviewers(self):
        assert _extract_requested_reviewers({"requested_reviewers": []}) == []

    def test_null_reviewers(self):
        assert _extract_requested_reviewers({"requested_reviewers": None}) == []

    def test_missing_reviewers_key(self):
        assert _extract_requested_reviewers({}) == []

    def test_deduplicated(self):
        item = {"requested_reviewers": [
            {"login": "alice"},
            {"login": "alice"},
        ]}
        assert _extract_requested_reviewers(item) == ["alice"]

    def test_malformed_reviewer_ignored(self):
        item = {"requested_reviewers": [
            {"login": "alice"},
            {"name": "no_login"},
            None,
            "string_reviewer",
        ]}
        assert _extract_requested_reviewers(item) == ["alice"]


# ---------------------------------------------------------------------------
# 4. Open Duration Calculation Tests
# ---------------------------------------------------------------------------

class TestCalculateOpenDurationHours:
    def test_open_pr_duration(self):
        """Open PR: duration = now - created_at."""
        created = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        duration = _calculate_open_duration_hours(created, None, None)
        assert 4.9 <= duration <= 5.2  # allow slight variance

    def test_closed_pr_duration(self):
        """Closed PR: duration = closed_at - created_at."""
        created = "2026-01-15T10:00:00+00:00"
        closed = "2026-01-15T22:00:00+00:00"
        duration = _calculate_open_duration_hours(created, closed, None)
        assert duration == 12.0

    def test_merged_pr_duration(self):
        """Merged PR: duration = merged_at - created_at (merged takes precedence)."""
        created = "2026-01-15T10:00:00+00:00"
        closed = "2026-01-15T22:00:00+00:00"
        merged = "2026-01-15T20:00:00+00:00"
        duration = _calculate_open_duration_hours(created, closed, merged)
        assert duration == 10.0

    def test_none_created_returns_zero(self):
        assert _calculate_open_duration_hours(None, None, None) == 0.0

    def test_invalid_created_returns_zero(self):
        assert _calculate_open_duration_hours("bad-date", None, None) == 0.0

    def test_never_negative(self):
        """If timestamps are somehow backwards, result is 0."""
        created = "2026-01-15T22:00:00+00:00"
        merged = "2026-01-15T10:00:00+00:00"
        duration = _calculate_open_duration_hours(created, None, merged)
        assert duration == 0.0


# ---------------------------------------------------------------------------
# 5. PR Normalization Tests
# ---------------------------------------------------------------------------

class TestNormalizePR:
    def test_normal_open_pr(self, sample_raw_pr, sample_repository, sample_details):
        result = _normalize_pr(sample_raw_pr, sample_repository, sample_details)
        assert result["number"] == 42
        assert result["title"] == "feat: add new feature"
        assert result["author"] == "testuser"
        assert result["state"] == "open"
        assert result["additions"] == 150
        assert result["deletions"] == 30
        assert result["reviews_count"] == 2
        assert result["requested_reviewers"] == ["reviewer1", "reviewer2"]
        assert result["merged_at"] is None
        assert result["closed_at"] is None

    def test_merged_pr(self, sample_repository, sample_details):
        raw = {
            "number": 10,
            "title": "Fix bug",
            "state": "closed",
            "user": {"login": "dev"},
            "created_at": "2026-01-10T08:00:00Z",
            "updated_at": "2026-01-12T10:00:00Z",
            "closed_at": "2026-01-12T10:00:00Z",
            "merged_at": "2026-01-12T10:00:00Z",
            "requested_reviewers": [],
            "html_url": "https://github.com/test/repo/pull/10",
        }
        result = _normalize_pr(raw, sample_repository, sample_details)
        assert result["state"] == "merged"
        assert result["merged_at"] is not None
        assert result["open_duration_hours"] == 50.0

    def test_missing_number_raises(self, sample_repository, sample_details):
        raw = {"title": "No number", "state": "open",
               "user": {"login": "x"}, "created_at": "2026-01-15T10:30:00Z"}
        with pytest.raises(GitHubAPIError, match="number"):
            _normalize_pr(raw, sample_repository, sample_details)

    def test_missing_title_raises(self, sample_repository, sample_details):
        raw = {"number": 1, "state": "open",
               "user": {"login": "x"}, "created_at": "2026-01-15T10:30:00Z"}
        with pytest.raises(GitHubAPIError, match="title"):
            _normalize_pr(raw, sample_repository, sample_details)

    def test_missing_created_at_raises(self, sample_repository, sample_details):
        raw = {"number": 1, "title": "Test", "state": "open",
               "user": {"login": "x"}}
        with pytest.raises(GitHubAPIError, match="created_at"):
            _normalize_pr(raw, sample_repository, sample_details)

    def test_boolean_number_raises(self, sample_repository, sample_details):
        raw = {"number": True, "title": "Test", "state": "open",
               "user": {"login": "x"}, "created_at": "2026-01-15T10:30:00Z"}
        with pytest.raises(GitHubAPIError, match="number"):
            _normalize_pr(raw, sample_repository, sample_details)

    def test_null_user_sets_unknown(self, sample_repository, sample_details):
        raw = {"number": 99, "title": "Test", "state": "open",
               "user": None, "created_at": "2026-01-15T10:30:00Z",
               "requested_reviewers": []}
        result = _normalize_pr(raw, sample_repository, sample_details)
        assert result["author"] == "Unknown"


# ---------------------------------------------------------------------------
# 6. GitHub API Error Response Tests
# ---------------------------------------------------------------------------

class TestRaiseForPRResponse:
    def _mock_response(self, status_code, headers=None, text="", json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = 200 <= status_code < 300
        resp.headers = headers or {}
        resp.text = text
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.return_value = {"message": text}
        return resp

    def test_401_raises_auth_error(self):
        resp = self._mock_response(401)
        with pytest.raises(GitHubAuthError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_429_raises_rate_limit(self):
        resp = self._mock_response(429)
        with pytest.raises(GitHubRateLimitError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_403_rate_limit_header(self):
        resp = self._mock_response(
            403,
            headers={"X-RateLimit-Remaining": "0"},
        )
        with pytest.raises(GitHubRateLimitError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_403_rate_limit_in_body(self):
        resp = self._mock_response(403, text="API rate limit exceeded")
        with pytest.raises(GitHubRateLimitError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_403_permission_error(self):
        resp = self._mock_response(403, text="Resource not accessible")
        with pytest.raises(GitHubPermissionError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_404_raises_not_found(self):
        resp = self._mock_response(404)
        with pytest.raises(GitHubRepoNotFoundError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_500_raises_api_error(self):
        resp = self._mock_response(500, text="Internal error")
        with pytest.raises(GitHubAPIError):
            _raise_for_pr_response(resp, "owner", "repo")

    def test_200_does_not_raise(self):
        resp = self._mock_response(200)
        _raise_for_pr_response(resp, "owner", "repo")  # should not raise


# ---------------------------------------------------------------------------
# 7. Pagination Tests
# ---------------------------------------------------------------------------

class TestFetchAllPRItems:
    @patch("Backend.externalservies.github_prs._request_pr_page")
    def test_single_page(self, mock_request):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.headers = {}
        resp.json.return_value = [{"number": 1}, {"number": 2}]
        resp.links = {}
        mock_request.return_value = resp

        session = MagicMock()
        items = _fetch_all_pr_items(session, "owner", "repo")
        assert len(items) == 2

    @patch("Backend.externalservies.github_prs._request_pr_page")
    def test_multiple_pages(self, mock_request):
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.ok = True
        resp1.headers = {}
        resp1.json.return_value = [{"number": 1}]
        resp1.links = {"next": {"url": "https://api.github.com/page2"}}

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.ok = True
        resp2.headers = {}
        resp2.json.return_value = [{"number": 2}]
        resp2.links = {}

        mock_request.side_effect = [resp1, resp2]

        session = MagicMock()
        items = _fetch_all_pr_items(session, "owner", "repo")
        assert len(items) == 2

    @patch("Backend.externalservies.github_prs._request_pr_page")
    def test_repeated_page_raises(self, mock_request):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.headers = {}
        resp.json.return_value = [{"number": 1}]
        url = "https://api.github.com/repos/owner/repo/pulls"
        resp.links = {"next": {"url": url}}
        mock_request.return_value = resp

        session = MagicMock()
        with pytest.raises(GitHubAPIError, match="repeated"):
            _fetch_all_pr_items(session, "owner", "repo")


# ---------------------------------------------------------------------------
# 8. Sync Workflow Tests
# ---------------------------------------------------------------------------

class TestSyncProjectPRs:
    @patch("Backend.externalservies.github_prs.upsert_pull_request")
    @patch("Backend.externalservies.github_prs.get_github_prs")
    @patch("Backend.externalservies.github_prs._resolve_repo_url")
    @patch("Backend.externalservies.github_prs.get_project")
    def test_successful_sync(self, mock_get_project, mock_resolve, mock_fetch, mock_upsert):
        mock_get_project.return_value = {"_id": "proj123", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r", "full_name": "o/r", "url": "https://github.com/o/r"},
            "pull_requests": [
                {"number": 1, "title": "PR 1"},
                {"number": 2, "title": "PR 2"},
            ],
        }
        mock_upsert.return_value = "id123"

        result = sync_project_prs("proj123")
        assert result["success"] is True
        assert result["status"] == "synced"
        assert result["fetched_count"] == 2
        assert mock_upsert.call_count == 2

    @patch("Backend.externalservies.github_prs.get_project")
    def test_empty_project_id_raises(self, mock_get_project):
        with pytest.raises(ValueError, match="project_id"):
            sync_project_prs("")

    @patch("Backend.externalservies.github_prs.get_project")
    def test_project_not_found_raises(self, mock_get_project):
        mock_get_project.return_value = None
        with pytest.raises(ProjectNotFoundError):
            sync_project_prs("nonexistent")

    @patch("Backend.externalservies.github_prs.upsert_pull_request")
    @patch("Backend.externalservies.github_prs.get_github_prs")
    @patch("Backend.externalservies.github_prs._resolve_repo_url")
    @patch("Backend.externalservies.github_prs.get_project")
    def test_empty_repo_syncs_zero(self, mock_get_project, mock_resolve, mock_fetch, mock_upsert):
        mock_get_project.return_value = {"_id": "proj123", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r", "full_name": "o/r", "url": "https://github.com/o/r"},
            "pull_requests": [],
        }

        result = sync_project_prs("proj123")
        assert result["fetched_count"] == 0
        assert mock_upsert.call_count == 0

    @patch("Backend.externalservies.github_prs.upsert_pull_request")
    @patch("Backend.externalservies.github_prs.get_github_prs")
    @patch("Backend.externalservies.github_prs._resolve_repo_url")
    @patch("Backend.externalservies.github_prs.get_project")
    def test_database_error_propagates(self, mock_get_project, mock_resolve, mock_fetch, mock_upsert):
        mock_get_project.return_value = {"_id": "proj123", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r", "full_name": "o/r", "url": "https://github.com/o/r"},
            "pull_requests": [{"number": 1, "title": "PR 1"}],
        }
        mock_upsert.side_effect = DatabaseError("DB failed")

        with pytest.raises(DatabaseError):
            sync_project_prs("proj123")


# ---------------------------------------------------------------------------
# 9. Get PRs from DB Tests
# ---------------------------------------------------------------------------

class TestGetPRsForProject:
    @patch("Backend.externalservies.github_prs.get_project_prs")
    def test_returns_formatted_prs(self, mock_get_prs):
        mock_get_prs.return_value = [
            {
                "_id": "id1",
                "projectId": "proj123",
                "number": 1,
                "title": "Test PR",
                "author": "dev",
                "state": "open",
                "created_at": "2026-01-15T10:00:00+00:00",
                "updated_at": "2026-01-16T10:00:00+00:00",
                "closed_at": None,
                "merged_at": None,
                "requested_reviewers": ["rev1"],
                "reviews_count": 1,
                "additions": 100,
                "deletions": 20,
                "open_duration_hours": 24.0,
                "html_url": "https://github.com/test/repo/pull/1",
            },
        ]

        result = get_prs_for_project("proj123")
        assert len(result) == 1
        assert result[0]["number"] == 1
        assert result[0]["id"] == "id1"

    @patch("Backend.externalservies.github_prs.get_project_prs")
    def test_state_filter(self, mock_get_prs):
        mock_get_prs.return_value = []
        get_prs_for_project("proj123", state="merged")
        mock_get_prs.assert_called_once_with("proj123", state="merged")

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="state"):
            get_prs_for_project("proj123", state="invalid")

    def test_empty_project_id_raises(self):
        with pytest.raises(ValueError, match="project_id"):
            get_prs_for_project("")


# ---------------------------------------------------------------------------
# 10. API Endpoint Tests (FastAPI TestClient)
# ---------------------------------------------------------------------------

class TestPREndpoints:
    """Test the GET /prs and POST /sync-prs endpoints via FastAPI TestClient."""

    def _override_auth(self, app, user):
        """Override authentication dependency."""
        from Backend.auth.dependencies import get_current_user
        from Backend.auth.roles import require_role, Role
        app.dependency_overrides[get_current_user] = lambda: user
        # Override role-based auth to return the same user
        for role_combo in [
            (Role.ADMIN,),
            (Role.ADMIN, Role.PROJECT_MANAGER),
            (Role.PROJECT_MANAGER,),
        ]:
            app.dependency_overrides[require_role(*role_combo)] = lambda: user

    def _clear_overrides(self, app):
        app.dependency_overrides.clear()

    @patch("Backend.routers.data_sync_router.get_prs_for_project")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_get_prs_endpoint(self, mock_parse, mock_require, mock_get_prs, test_client, mock_user):
        self._override_auth(app, mock_user)
        mock_require.return_value = {"_id": "proj123"}
        mock_get_prs.return_value = [
            {
                "id": "id1",
                "project_id": "proj123",
                "number": 1,
                "title": "Test PR",
                "author": "dev",
                "state": "open",
                "created_at": "2026-01-15T10:00:00+00:00",
                "updated_at": None,
                "closed_at": None,
                "merged_at": None,
                "requested_reviewers": [],
                "reviews_count": 0,
                "additions": 10,
                "deletions": 5,
                "open_duration_hours": 24.0,
                "html_url": None,
            },
        ]

        resp = test_client.get("/api/projects/507f1f77bcf86cd799439022/prs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["number"] == 1

        self._clear_overrides(app)

    @patch("Backend.routers.data_sync_router.get_prs_for_project")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_get_prs_with_state_filter(self, mock_parse, mock_require, mock_get_prs, test_client, mock_user):
        self._override_auth(app, mock_user)
        mock_require.return_value = {"_id": "proj123"}
        mock_get_prs.return_value = []

        resp = test_client.get("/api/projects/507f1f77bcf86cd799439022/prs?state=merged")
        assert resp.status_code == 200
        mock_get_prs.assert_called_once_with("507f1f77bcf86cd799439022", state="merged")

        self._clear_overrides(app)

    @patch("Backend.routers.data_sync_router.get_prs_for_project")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_get_prs_invalid_state_returns_422(self, mock_parse, mock_require, mock_get_prs, test_client, mock_user):
        self._override_auth(app, mock_user)
        mock_require.return_value = {"_id": "proj123"}

        resp = test_client.get("/api/projects/507f1f77bcf86cd799439022/prs?state=invalid")
        assert resp.status_code == 422

        self._clear_overrides(app)

    @patch("Backend.routers.data_sync_router.sync_project_prs")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_sync_prs_endpoint(self, mock_parse, mock_require, mock_sync, test_client, mock_user):
        self._override_auth(app, mock_user)
        mock_require.return_value = {"_id": "proj123"}
        mock_sync.return_value = {
            "success": True,
            "status": "synced",
            "project_id": "proj123",
            "repository": {"owner": "o", "name": "r", "full_name": "o/r", "url": "https://github.com/o/r"},
            "fetched_count": 5,
            "created_count": 3,
            "updated_count": 2,
        }

        resp = test_client.post("/api/projects/507f1f77bcf86cd799439022/sync-prs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["fetched_count"] == 5

        self._clear_overrides(app)

    @patch("Backend.routers.data_sync_router.sync_project_prs")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_sync_prs_with_repo_url(self, mock_parse, mock_require, mock_sync, test_client, mock_user):
        self._override_auth(app, mock_user)
        mock_require.return_value = {"_id": "proj123"}
        mock_sync.return_value = {
            "success": True,
            "status": "synced",
            "project_id": "proj123",
            "repository": {"owner": "o", "name": "r", "full_name": "o/r", "url": "https://github.com/o/r"},
            "fetched_count": 0,
            "created_count": 0,
            "updated_count": 0,
        }

        resp = test_client.post(
            "/api/projects/507f1f77bcf86cd799439022/sync-prs",
            json={"repo_url": "https://github.com/o/r"},
        )
        assert resp.status_code == 200

        self._clear_overrides(app)


# ---------------------------------------------------------------------------
# 11. Edge Case Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_pr_with_no_reviewers(self, sample_repository, sample_details):
        raw = {
            "number": 1,
            "title": "Solo PR",
            "state": "open",
            "user": {"login": "dev"},
            "created_at": "2026-01-15T10:30:00Z",
            "requested_reviewers": [],
        }
        result = _normalize_pr(raw, sample_repository, sample_details)
        assert result["requested_reviewers"] == []

    def test_pr_with_empty_additions_deletions(self, sample_repository):
        raw = {
            "number": 1,
            "title": "Empty PR",
            "state": "open",
            "user": {"login": "dev"},
            "created_at": "2026-01-15T10:30:00Z",
            "requested_reviewers": [],
        }
        details = {"additions": 0, "deletions": 0, "reviews_count": 0}
        result = _normalize_pr(raw, sample_repository, details)
        assert result["additions"] == 0
        assert result["deletions"] == 0

    def test_open_duration_boundary_zero_seconds(self):
        """PR created and merged at the same time."""
        ts = "2026-01-15T10:00:00+00:00"
        duration = _calculate_open_duration_hours(ts, ts, ts)
        assert duration == 0.0

    def test_very_long_duration(self):
        """PR open for 30 days."""
        created = "2026-01-01T00:00:00+00:00"
        closed = "2026-01-31T00:00:00+00:00"
        duration = _calculate_open_duration_hours(created, closed, None)
        assert duration == 720.0  # 30 * 24


# ---------------------------------------------------------------------------
# 12. Deduplication Tests
# ---------------------------------------------------------------------------

class TestDeduplication:
    @patch("Backend.externalservies.github_prs.upsert_pull_request")
    @patch("Backend.externalservies.github_prs.get_github_prs")
    @patch("Backend.externalservies.github_prs._resolve_repo_url")
    @patch("Backend.externalservies.github_prs.get_project")
    def test_same_pr_synced_twice_calls_upsert(self, mock_get_project, mock_resolve, mock_fetch, mock_upsert):
        """Running sync twice should upsert (not duplicate) the same PRs."""
        mock_get_project.return_value = {"_id": "proj123", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r", "full_name": "o/r", "url": "https://github.com/o/r"},
            "pull_requests": [{"number": 1, "title": "PR 1"}],
        }
        mock_upsert.return_value = "id123"

        # Sync twice
        sync_project_prs("proj123")
        sync_project_prs("proj123")

        # upsert was called with the same PR number both times — no duplicates
        assert mock_upsert.call_count == 2
        calls = mock_upsert.call_args_list
        assert calls[0][0][0] == "proj123"  # project_id
        assert calls[1][0][0] == "proj123"


# ---------------------------------------------------------------------------
# 13. Security Tests
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_no_token_in_error_messages(self):
        """Error messages should never contain the GitHub token."""
        resp = MagicMock()
        resp.status_code = 401
        resp.ok = False
        resp.text = "Bad credentials"
        resp.headers = {}

        try:
            _raise_for_pr_response(resp, "owner", "repo")
        except GitHubAuthError as e:
            msg = str(e)
            assert "ghp_" not in msg
            assert "token" not in msg.lower() or "GITHUB_TOKEN" in msg

    def test_present_pr_does_not_leak_internal_fields(self):
        """_present_pr should only return whitelisted fields."""
        from Backend.externalservies.github_prs import _present_pr

        document = {
            "_id": "id1",
            "projectId": "proj123",
            "number": 1,
            "title": "Test",
            "author": "dev",
            "state": "open",
            "created_at": "2026-01-15T10:00:00+00:00",
            "updated_at": None,
            "closed_at": None,
            "merged_at": None,
            "requested_reviewers": [],
            "reviews_count": 0,
            "additions": 10,
            "deletions": 5,
            "open_duration_hours": 24.0,
            "html_url": None,
            "last_synced_at": "2026-01-16T00:00:00+00:00",  # internal field
            "repository_url": "https://github.com/o/r",  # internal field
            "github_username": "dev",  # internal field
        }

        result = _present_pr(document)
        assert "last_synced_at" not in result
        assert "repository_url" not in result
        assert "github_username" not in result

    def test_present_pr_derives_reviews_count_from_reviews_list(self):
        """If document has 'reviews' array without 'reviews_count', calculate it."""
        from Backend.externalservies.github_prs import _present_pr

        document = {
            "_id": "id2",
            "projectId": "proj123",
            "number": 2,
            "title": "PR with reviews",
            "reviews": [{"id": 101}, {"id": 102}, {"id": 103}],
            "state": "open",
        }
        result = _present_pr(document)
        assert result["reviews_count"] == 3


# ---------------------------------------------------------------------------
# 14. Network Failure Tests
# ---------------------------------------------------------------------------

class TestNetworkFailures:
    @patch("Backend.externalservies.github_prs._request_pr_page")
    def test_timeout_raises_api_error(self, mock_request):
        import requests as req
        mock_request.side_effect = GitHubAPIError("Request to GitHub timed out")

        session = MagicMock()
        with pytest.raises(GitHubAPIError, match="timed out"):
            _fetch_all_pr_items(session, "owner", "repo")

    @patch("Backend.externalservies.github_prs._request_pr_page")
    def test_connection_error_raises(self, mock_request):
        mock_request.side_effect = GitHubAPIError("Could not connect to GitHub")

        session = MagicMock()
        with pytest.raises(GitHubAPIError, match="connect"):
            _fetch_all_pr_items(session, "owner", "repo")


# ---------------------------------------------------------------------------
# 15. Integration Test (Full Flow Mock)
# ---------------------------------------------------------------------------

class TestIntegrationFlow:
    @patch("Backend.externalservies.github_prs.upsert_pull_request")
    @patch("Backend.externalservies.github_prs._fetch_pr_details")
    @patch("Backend.externalservies.github_prs._fetch_all_pr_items")
    @patch("Backend.externalservies.github_prs._get_authenticated_session")
    @patch("Backend.externalservies.github_prs._parse_github_url")
    @patch("Backend.externalservies.github_prs._resolve_repo_url")
    @patch("Backend.externalservies.github_prs.get_project")
    def test_full_sync_flow(
        self,
        mock_get_project,
        mock_resolve,
        mock_parse_url,
        mock_session,
        mock_fetch_all,
        mock_fetch_details,
        mock_upsert,
    ):
        mock_get_project.return_value = {
            "_id": "proj123",
            "repo_url": "https://github.com/OpenTirZ/test-repo",
        }
        mock_resolve.return_value = "https://github.com/OpenTirZ/test-repo"
        mock_parse_url.return_value = ("OpenTirZ", "test-repo")
        mock_session.return_value = MagicMock()

        mock_fetch_all.return_value = [
            {
                "number": 1,
                "title": "feat: add login",
                "state": "closed",
                "user": {"login": "alice"},
                "created_at": "2026-01-10T08:00:00Z",
                "updated_at": "2026-01-12T10:00:00Z",
                "closed_at": "2026-01-12T10:00:00Z",
                "merged_at": "2026-01-12T10:00:00Z",
                "requested_reviewers": [{"login": "bob"}],
                "html_url": "https://github.com/OpenTirZ/test-repo/pull/1",
            },
            {
                "number": 2,
                "title": "fix: typo",
                "state": "open",
                "user": {"login": "charlie"},
                "created_at": "2026-01-14T12:00:00Z",
                "updated_at": "2026-01-14T12:00:00Z",
                "closed_at": None,
                "merged_at": None,
                "requested_reviewers": [],
                "html_url": "https://github.com/OpenTirZ/test-repo/pull/2",
            },
        ]

        mock_fetch_details.return_value = {
            "additions": 50,
            "deletions": 10,
            "reviews_count": 1,
        }
        mock_upsert.return_value = "inserted_id"

        result = sync_project_prs("proj123")

        assert result["success"] is True
        assert result["fetched_count"] == 2
        assert result["created_count"] == 2
        assert mock_upsert.call_count == 2

        # Verify the first PR was normalized correctly
        first_call_pr = mock_upsert.call_args_list[0][0][1]
        assert first_call_pr["state"] == "merged"
        assert first_call_pr["author"] == "alice"
        assert first_call_pr["requested_reviewers"] == ["bob"]
