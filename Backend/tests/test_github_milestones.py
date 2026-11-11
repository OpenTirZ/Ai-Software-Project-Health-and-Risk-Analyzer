"""
Test Suite — GitHub Milestone Synchronization (Issue #72, TASK-SP2-08)
======================================================================

Tests:
    - Milestone normalization (fields, state, timestamps)
    - Completion percentage calculation (div-by-zero, boundaries)
    - GitHub API error handling (401, 403, 404, 422, 429, 500, timeout)
    - Pagination (single, multi-page, empty)
    - Sync workflow (fetch + persist)
    - GET endpoint (read from DB, no GitHub calls)
    - POST endpoint (sync from GitHub)
    - Empty milestone handling ("Insufficient milestone data")
    - Deduplication / idempotency
    - Cross-project isolation
    - Authorization (role-based access)
    - Security (no secret leakage)
    - No unnecessary GitHub API calls
    - Database failure handling

All tests use mocking — NO real GitHub or MongoDB calls.

Author: Prince Savaliya
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Environment setup — must happen BEFORE importing Backend modules
# ---------------------------------------------------------------------------
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_milestone_db")
os.environ.setdefault("MONGO_DATABASE", "test_milestone_db")
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


import pymongo
_original_MongoClient = pymongo.MongoClient
pymongo.MongoClient = _mock_mongo_client

try:
    from Backend.externalservies.github_milestones import (
        GitHubPermissionError,
        GitHubRateLimitError,
        _fetch_milestones_by_state,
        _fetch_all_milestones,
        _normalize_milestone,
        _normalize_timestamp,
        _present_milestone,
        _raise_for_milestone_response,
        _safe_int,
        calculate_completion_percentage,
        map_issues_to_milestones,
        get_github_milestones,
        get_milestones_for_project,
        sync_project_milestones,
    )
    from Backend.externalservies.github_commits import (
        GitHubAPIError,
        GitHubAuthError,
        GitHubRepoNotFoundError,
        GitHubTokenMissingError,
    )
    from Backend.externalservies.contributor_service import ProjectNotFoundError
    from Backend.persistence import DatabaseError
    from Backend.main import app

    from fastapi.testclient import TestClient
finally:
    pymongo.MongoClient = _original_MongoClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    """FastAPI test client with mocked authentication."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_user():
    return {
        "_id": "507f1f77bcf86cd799439011",
        "email": "test@example.com",
        "name": "Test User",
        "role": "admin",
    }


@pytest.fixture
def mock_project():
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
def sample_raw_milestone():
    """A raw milestone as returned by GitHub API."""
    return {
        "number": 1,
        "id": 12345,
        "title": "Sprint 1",
        "description": "First sprint milestone",
        "state": "open",
        "due_on": "2026-02-01T00:00:00Z",
        "open_issues": 5,
        "closed_issues": 10,
        "html_url": "https://github.com/test/repo/milestone/1",
    }


@pytest.fixture
def sample_repository():
    return {
        "owner": "OpenTirZ",
        "name": "Ai-Software-Project-Health-and-Risk-Analyzer",
        "full_name": "OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
        "url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
    }


# ===========================================================================
# 1. Completion Percentage Tests
# ===========================================================================

class TestCompletionPercentage:
    def test_equal_open_closed(self):
        assert calculate_completion_percentage(5, 5) == 50.0

    def test_all_closed(self):
        assert calculate_completion_percentage(0, 10) == 100.0

    def test_all_open(self):
        assert calculate_completion_percentage(10, 0) == 0.0

    def test_zero_zero_no_crash(self):
        """Division by zero must return 0.0, not NaN or Infinity."""
        result = calculate_completion_percentage(0, 0)
        assert result == 0.0
        # Verify it's a real float, not NaN
        assert result == result  # NaN != NaN

    def test_large_numbers(self):
        assert calculate_completion_percentage(0, 1000000) == 100.0

    def test_rounding(self):
        result = calculate_completion_percentage(1, 2)
        assert result == 66.67

    def test_one_third(self):
        result = calculate_completion_percentage(2, 1)
        assert result == 33.33

    def test_never_exceeds_100(self):
        """Even with weird inputs, result stays in [0, 100]."""
        result = calculate_completion_percentage(0, 999999)
        assert 0.0 <= result <= 100.0


# ===========================================================================
# 1b. Issue-to-Milestone Mapping Tests
# ===========================================================================

class TestMapIssuesToMilestones:
    def test_maps_issues_to_corresponding_milestones(self):
        milestones = [
            {"milestone_id": "1", "title": "Milestone 1"},
            {"milestone_id": "2", "title": "Milestone 2"},
        ]
        issues = [
            {"number": 101, "title": "Issue A", "milestone": {"number": 1}},
            {"number": 102, "title": "Issue B", "milestone": {"number": 2}},
            {"number": 103, "title": "Issue C", "milestone": {"number": 1}},
            {"number": 104, "title": "Issue D", "milestone": None},
        ]
        result = map_issues_to_milestones(milestones, issues)

        assert len(result["1"]) == 2
        assert [i["number"] for i in result["1"]] == [101, 103]
        assert len(result["2"]) == 1
        assert [i["number"] for i in result["2"]] == [102]
        assert len(result["__unassigned__"]) == 1
        assert result["__unassigned__"][0]["number"] == 104

    def test_handles_string_milestone_ref(self):
        milestones = [{"milestone_id": "1", "title": "Milestone 1"}]
        issues = [{"number": 1, "milestone": "1"}]
        result = map_issues_to_milestones(milestones, issues)
        assert len(result["1"]) == 1

    def test_unrecognized_milestone_goes_to_unassigned(self):
        milestones = [{"milestone_id": "1", "title": "Milestone 1"}]
        issues = [{"number": 1, "milestone": {"number": 99}}]
        result = map_issues_to_milestones(milestones, issues)
        assert len(result["1"]) == 0
        assert len(result["__unassigned__"]) == 1

    def test_empty_milestones_and_issues(self):
        result = map_issues_to_milestones([], [])
        assert result == {"__unassigned__": []}


# ===========================================================================
# 2. _safe_int Tests
# ===========================================================================

class TestSafeInt:
    def test_normal_int(self):
        assert _safe_int(42) == 42

    def test_none_returns_default(self):
        assert _safe_int(None) == 0

    def test_negative_returns_default(self):
        assert _safe_int(-5) == 0

    def test_bool_returns_default(self):
        assert _safe_int(True) == 0
        assert _safe_int(False) == 0

    def test_string_number(self):
        assert _safe_int("10") == 10

    def test_invalid_string(self):
        assert _safe_int("not a number") == 0

    def test_float_truncated(self):
        assert _safe_int(3.9) == 3

    def test_custom_default(self):
        assert _safe_int(None, default=99) == 99


# ===========================================================================
# 3. Timestamp Normalization Tests
# ===========================================================================

class TestNormalizeTimestamp:
    def test_valid_utc(self):
        result = _normalize_timestamp("2026-01-15T10:30:00Z", "due_on")
        assert result is not None
        assert "+00:00" in result

    def test_none_returns_none(self):
        assert _normalize_timestamp(None, "due_on") is None

    def test_empty_returns_none(self):
        assert _normalize_timestamp("", "due_on") is None

    def test_invalid_type_raises(self):
        with pytest.raises(GitHubAPIError, match="invalid"):
            _normalize_timestamp(12345, "due_on")

    def test_invalid_format_raises(self):
        with pytest.raises(GitHubAPIError, match="invalid"):
            _normalize_timestamp("not-a-date", "due_on")


# ===========================================================================
# 4. Milestone Normalization Tests
# ===========================================================================

class TestNormalizeMilestone:
    def test_normal_milestone(self, sample_raw_milestone):
        result = _normalize_milestone(sample_raw_milestone)
        assert result["milestone_id"] == "1"
        assert result["title"] == "Sprint 1"
        assert result["description"] == "First sprint milestone"
        assert result["state"] == "open"
        assert result["open_issues"] == 5
        assert result["closed_issues"] == 10
        assert result["completion_percentage"] == 66.67
        assert result["due_on"] is not None

    def test_closed_milestone(self):
        raw = {
            "number": 2,
            "title": "Sprint 2",
            "state": "closed",
            "open_issues": 0,
            "closed_issues": 20,
        }
        result = _normalize_milestone(raw)
        assert result["state"] == "closed"
        assert result["completion_percentage"] == 100.0

    def test_no_issues(self):
        raw = {"number": 3, "title": "Empty Sprint", "state": "open",
               "open_issues": 0, "closed_issues": 0}
        result = _normalize_milestone(raw)
        assert result["completion_percentage"] == 0.0

    def test_missing_number_uses_id(self):
        raw = {"id": 999, "title": "Fallback ID", "state": "open"}
        result = _normalize_milestone(raw)
        assert result["milestone_id"] == "999"

    def test_missing_number_and_id_raises(self):
        raw = {"title": "No ID", "state": "open"}
        with pytest.raises(GitHubAPIError, match="identifier"):
            _normalize_milestone(raw)

    def test_boolean_number_raises(self):
        raw = {"number": True, "title": "Boolean", "state": "open"}
        with pytest.raises(GitHubAPIError, match="identifier"):
            _normalize_milestone(raw)

    def test_missing_title_gets_default(self):
        raw = {"number": 1, "state": "open"}
        result = _normalize_milestone(raw)
        assert result["title"] == "Untitled Milestone"

    def test_empty_title_gets_default(self):
        raw = {"number": 1, "title": "", "state": "open"}
        result = _normalize_milestone(raw)
        assert result["title"] == "Untitled Milestone"

    def test_null_description(self):
        raw = {"number": 1, "title": "Test", "state": "open",
               "description": None}
        result = _normalize_milestone(raw)
        assert result["description"] == ""

    def test_null_due_on(self):
        raw = {"number": 1, "title": "Test", "state": "open",
               "due_on": None}
        result = _normalize_milestone(raw)
        assert result["due_on"] is None

    def test_invalid_state_defaults_to_open(self):
        raw = {"number": 1, "title": "Test", "state": "weird"}
        result = _normalize_milestone(raw)
        assert result["state"] == "open"

    def test_negative_issue_counts_become_zero(self):
        raw = {"number": 1, "title": "Test", "state": "open",
               "open_issues": -5, "closed_issues": -10}
        result = _normalize_milestone(raw)
        assert result["open_issues"] == 0
        assert result["closed_issues"] == 0
        assert result["completion_percentage"] == 0.0

    def test_string_issue_counts_handled(self):
        raw = {"number": 1, "title": "Test", "state": "open",
               "open_issues": "3", "closed_issues": "7"}
        result = _normalize_milestone(raw)
        assert result["open_issues"] == 3
        assert result["closed_issues"] == 7
        assert result["completion_percentage"] == 70.0

    def test_none_issue_counts_handled(self):
        raw = {"number": 1, "title": "Test", "state": "open",
               "open_issues": None, "closed_issues": None}
        result = _normalize_milestone(raw)
        assert result["open_issues"] == 0
        assert result["closed_issues"] == 0


# ===========================================================================
# 5. GitHub API Error Response Tests
# ===========================================================================

class TestRaiseForMilestoneResponse:
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
        with pytest.raises(GitHubAuthError):
            _raise_for_milestone_response(
                self._mock_response(401), "o", "r")

    def test_429_raises_rate_limit(self):
        with pytest.raises(GitHubRateLimitError):
            _raise_for_milestone_response(
                self._mock_response(429), "o", "r")

    def test_403_rate_limit_header(self):
        resp = self._mock_response(
            403, headers={"X-RateLimit-Remaining": "0"})
        with pytest.raises(GitHubRateLimitError):
            _raise_for_milestone_response(resp, "o", "r")

    def test_403_rate_limit_in_body(self):
        resp = self._mock_response(403, text="API rate limit exceeded")
        with pytest.raises(GitHubRateLimitError):
            _raise_for_milestone_response(resp, "o", "r")

    def test_403_permission(self):
        resp = self._mock_response(403, text="Resource not accessible")
        with pytest.raises(GitHubPermissionError):
            _raise_for_milestone_response(resp, "o", "r")

    def test_404_not_found(self):
        with pytest.raises(GitHubRepoNotFoundError):
            _raise_for_milestone_response(
                self._mock_response(404), "o", "r")

    def test_422_raises_api_error(self):
        with pytest.raises(GitHubAPIError):
            _raise_for_milestone_response(
                self._mock_response(422, text="Validation"), "o", "r")

    def test_500_raises_api_error(self):
        with pytest.raises(GitHubAPIError):
            _raise_for_milestone_response(
                self._mock_response(500, text="Internal"), "o", "r")

    def test_200_does_not_raise(self):
        _raise_for_milestone_response(
            self._mock_response(200), "o", "r")  # no exception


# ===========================================================================
# 6. Pagination Tests
# ===========================================================================

class TestFetchMilestonesByState:
    @patch("Backend.externalservies.github_milestones._request_milestone_page")
    def test_single_page(self, mock_request):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.headers = {}
        resp.json.return_value = [{"number": 1}, {"number": 2}]
        mock_request.return_value = resp

        session = MagicMock()
        items = _fetch_milestones_by_state(session, "o", "r", "open")
        assert len(items) == 2
        # Only 1 request because items < per_page
        assert mock_request.call_count == 1

    @patch("Backend.externalservies.github_milestones._request_milestone_page")
    def test_multiple_pages(self, mock_request):
        """Simulate: page1=100 items, page2=25 items."""
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.ok = True
        resp1.headers = {}
        resp1.json.return_value = [{"number": i} for i in range(100)]

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.ok = True
        resp2.headers = {}
        resp2.json.return_value = [{"number": i} for i in range(100, 125)]

        mock_request.side_effect = [resp1, resp2]

        session = MagicMock()
        items = _fetch_milestones_by_state(session, "o", "r", "open")
        assert len(items) == 125
        assert mock_request.call_count == 2

    @patch("Backend.externalservies.github_milestones._request_milestone_page")
    def test_empty_page_terminates(self, mock_request):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.headers = {}
        resp.json.return_value = []
        mock_request.return_value = resp

        session = MagicMock()
        items = _fetch_milestones_by_state(session, "o", "r", "open")
        assert len(items) == 0
        assert mock_request.call_count == 1

    @patch("Backend.externalservies.github_milestones._request_milestone_page")
    def test_page4_not_requested_when_page3_partial(self, mock_request):
        """page1=100, page2=100, page3=25 → page4 NOT requested."""
        pages = [
            [{"number": i} for i in range(100)],
            [{"number": i} for i in range(100, 200)],
            [{"number": i} for i in range(200, 225)],
        ]
        responses = []
        for page_data in pages:
            r = MagicMock()
            r.status_code = 200
            r.ok = True
            r.headers = {}
            r.json.return_value = page_data
            responses.append(r)
        mock_request.side_effect = responses

        session = MagicMock()
        items = _fetch_milestones_by_state(session, "o", "r", "open")
        assert len(items) == 225
        assert mock_request.call_count == 3  # NOT 4


class TestFetchAllMilestones:
    @patch("Backend.externalservies.github_milestones._fetch_milestones_by_state")
    def test_combines_open_and_closed(self, mock_fetch):
        mock_fetch.side_effect = [
            [{"number": 1, "state": "open"}],
            [{"number": 2, "state": "closed"}],
        ]
        session = MagicMock()
        items = _fetch_all_milestones(session, "o", "r")
        assert len(items) == 2
        assert mock_fetch.call_count == 2
        mock_fetch.assert_any_call(session, "o", "r", "open")
        mock_fetch.assert_any_call(session, "o", "r", "closed")


# ===========================================================================
# 7. Sync Workflow Tests
# ===========================================================================

class TestSyncProjectMilestones:
    @patch("Backend.externalservies.github_milestones.upsert_milestone")
    @patch("Backend.externalservies.github_milestones.get_github_milestones")
    @patch("Backend.externalservies.github_milestones._resolve_repo_url")
    @patch("Backend.externalservies.github_milestones.get_project")
    def test_successful_sync(self, mock_proj, mock_resolve, mock_fetch, mock_upsert):
        mock_proj.return_value = {"_id": "p1", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "milestones": [
                {"milestone_id": "1", "title": "S1"},
                {"milestone_id": "2", "title": "S2"},
            ],
        }
        mock_upsert.return_value = "id"

        result = sync_project_milestones("p1")
        assert result["success"] is True
        assert result["status"] == "synced"
        assert result["fetched_count"] == 2
        assert result["created_count"] == 2
        assert mock_upsert.call_count == 2

    @patch("Backend.externalservies.github_milestones.get_project")
    def test_empty_project_id_raises(self, mock_proj):
        with pytest.raises(ValueError, match="project_id"):
            sync_project_milestones("")

    @patch("Backend.externalservies.github_milestones.get_project")
    def test_project_not_found_raises(self, mock_proj):
        mock_proj.return_value = None
        with pytest.raises(ProjectNotFoundError):
            sync_project_milestones("nonexistent")

    @patch("Backend.externalservies.github_milestones.get_github_milestones")
    @patch("Backend.externalservies.github_milestones._resolve_repo_url")
    @patch("Backend.externalservies.github_milestones.get_project")
    def test_empty_milestones_returns_insufficient(
        self, mock_proj, mock_resolve, mock_fetch
    ):
        """Repos with 0 milestones must return 'Insufficient milestone data'."""
        mock_proj.return_value = {"_id": "p1", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "milestones": [],
        }

        result = sync_project_milestones("p1")
        assert result["success"] is True
        assert result["status"] == "no_milestones"
        assert result["fetched_count"] == 0
        assert result["message"] == "Insufficient milestone data"

    @patch("Backend.externalservies.github_milestones.upsert_milestone")
    @patch("Backend.externalservies.github_milestones.get_github_milestones")
    @patch("Backend.externalservies.github_milestones._resolve_repo_url")
    @patch("Backend.externalservies.github_milestones.get_project")
    def test_database_error_propagates(
        self, mock_proj, mock_resolve, mock_fetch, mock_upsert
    ):
        mock_proj.return_value = {"_id": "p1", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "milestones": [{"milestone_id": "1", "title": "S1"}],
        }
        mock_upsert.side_effect = DatabaseError("DB failed")

        with pytest.raises(DatabaseError):
            sync_project_milestones("p1")


# ===========================================================================
# 8. Get Milestones from DB Tests
# ===========================================================================

class TestGetMilestonesForProject:
    @patch("Backend.externalservies.github_milestones.get_project_milestones")
    def test_returns_formatted_milestones(self, mock_get):
        mock_get.return_value = [
            {
                "_id": "id1",
                "projectId": "p1",
                "milestone_id": "1",
                "title": "Sprint 1",
                "description": "desc",
                "state": "open",
                "due_on": "2026-02-01T00:00:00+00:00",
                "open_issues": 3,
                "closed_issues": 7,
                "html_url": "https://github.com/o/r/milestone/1",
            },
        ]

        result = get_milestones_for_project("p1")
        assert len(result) == 1
        assert result[0]["milestone_id"] == "1"
        assert result[0]["completion_percentage"] == 70.0

    @patch("Backend.externalservies.github_milestones.get_project_milestones")
    def test_state_filter_passed(self, mock_get):
        mock_get.return_value = []
        get_milestones_for_project("p1", state="closed")
        mock_get.assert_called_once_with("p1", state="closed")

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="state"):
            get_milestones_for_project("p1", state="merged")

    def test_empty_project_id_raises(self):
        with pytest.raises(ValueError, match="project_id"):
            get_milestones_for_project("")


# ===========================================================================
# 9. Deduplication / Idempotency Tests
# ===========================================================================

class TestDeduplication:
    @patch("Backend.externalservies.github_milestones.upsert_milestone")
    @patch("Backend.externalservies.github_milestones.get_github_milestones")
    @patch("Backend.externalservies.github_milestones._resolve_repo_url")
    @patch("Backend.externalservies.github_milestones.get_project")
    def test_same_milestone_synced_twice(
        self, mock_proj, mock_resolve, mock_fetch, mock_upsert
    ):
        """Running sync twice calls upsert_milestone twice with same data."""
        mock_proj.return_value = {"_id": "p1", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "milestones": [{"milestone_id": "1", "title": "S1"}],
        }
        mock_upsert.return_value = "id"

        sync_project_milestones("p1")
        sync_project_milestones("p1")

        assert mock_upsert.call_count == 2
        # Both calls upsert the same milestone — DB compound index handles dedup
        for c in mock_upsert.call_args_list:
            assert c[0][0] == "p1"


# ===========================================================================
# 10. Cross-Project Isolation Tests
# ===========================================================================

class TestCrossProjectIsolation:
    @patch("Backend.externalservies.github_milestones.upsert_milestone")
    @patch("Backend.externalservies.github_milestones.get_github_milestones")
    @patch("Backend.externalservies.github_milestones._resolve_repo_url")
    @patch("Backend.externalservies.github_milestones.get_project")
    def test_same_milestone_id_different_projects(
        self, mock_proj, mock_resolve, mock_fetch, mock_upsert
    ):
        """milestone_id=1 in project A and project B are separate records."""
        mock_resolve.return_value = "https://github.com/o/r"
        milestone = {"milestone_id": "1", "title": "S1"}
        mock_fetch.return_value = {
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "milestones": [milestone],
        }
        mock_upsert.return_value = "id"

        mock_proj.return_value = {"_id": "projA", "repo_url": "https://github.com/o/r"}
        sync_project_milestones("projA")

        mock_proj.return_value = {"_id": "projB", "repo_url": "https://github.com/o/r"}
        sync_project_milestones("projB")

        assert mock_upsert.call_count == 2
        assert mock_upsert.call_args_list[0][0][0] == "projA"
        assert mock_upsert.call_args_list[1][0][0] == "projB"


# ===========================================================================
# 11. API Endpoint Tests (FastAPI TestClient)
# ===========================================================================

class TestMilestoneEndpoints:
    def _override_auth(self, user):
        from Backend.auth.dependencies import get_current_user
        from Backend.auth.roles import require_role, Role
        app.dependency_overrides[get_current_user] = lambda: user
        for combo in [
            (Role.ADMIN,),
            (Role.ADMIN, Role.PROJECT_MANAGER),
            (Role.PROJECT_MANAGER,),
        ]:
            app.dependency_overrides[require_role(*combo)] = lambda: user

    def _clear(self):
        app.dependency_overrides.clear()

    @patch("Backend.routers.data_sync_router.get_milestones_for_project")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_get_milestones(
        self, mock_parse, mock_require, mock_get, test_client, mock_user
    ):
        self._override_auth(mock_user)
        mock_require.return_value = {"_id": "p1"}
        mock_get.return_value = [
            {
                "id": "id1", "project_id": "p1",
                "milestone_id": "1", "title": "Sprint 1",
                "description": "", "state": "open",
                "due_on": None, "open_issues": 5,
                "closed_issues": 10,
                "completion_percentage": 66.67,
                "html_url": "",
            },
        ]

        resp = test_client.get("/api/projects/507f1f77bcf86cd799439022/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["milestone_id"] == "1"
        assert data[0]["completion_percentage"] == 66.67
        self._clear()

    @patch("Backend.routers.data_sync_router.get_milestones_for_project")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_get_milestones_with_state_filter(
        self, mock_parse, mock_require, mock_get, test_client, mock_user
    ):
        self._override_auth(mock_user)
        mock_require.return_value = {"_id": "p1"}
        mock_get.return_value = []

        resp = test_client.get(
            "/api/projects/507f1f77bcf86cd799439022/milestones?state=closed"
        )
        assert resp.status_code == 200
        mock_get.assert_called_once_with("507f1f77bcf86cd799439022", state="closed")
        self._clear()

    @patch("Backend.routers.data_sync_router.get_milestones_for_project")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_get_milestones_invalid_state_422(
        self, mock_parse, mock_require, mock_get, test_client, mock_user
    ):
        self._override_auth(mock_user)
        mock_require.return_value = {"_id": "p1"}

        resp = test_client.get(
            "/api/projects/507f1f77bcf86cd799439022/milestones?state=invalid"
        )
        assert resp.status_code == 422
        self._clear()

    @patch("Backend.routers.data_sync_router.sync_project_milestones")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_sync_milestones(
        self, mock_parse, mock_require, mock_sync, test_client, mock_user
    ):
        self._override_auth(mock_user)
        mock_require.return_value = {"_id": "p1"}
        mock_sync.return_value = {
            "success": True, "status": "synced",
            "project_id": "p1",
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "fetched_count": 3, "created_count": 3,
            "updated_count": 0, "message": None,
        }

        resp = test_client.post(
            "/api/projects/507f1f77bcf86cd799439022/sync-milestones"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["fetched_count"] == 3
        self._clear()

    @patch("Backend.routers.data_sync_router.sync_project_milestones")
    @patch("Backend.routers.data_sync_router._require_project_member")
    @patch("Backend.routers.data_sync_router._parse_object_id")
    def test_sync_empty_returns_insufficient(
        self, mock_parse, mock_require, mock_sync, test_client, mock_user
    ):
        """Empty milestones must return 'Insufficient milestone data'."""
        self._override_auth(mock_user)
        mock_require.return_value = {"_id": "p1"}
        mock_sync.return_value = {
            "success": True, "status": "no_milestones",
            "project_id": "p1",
            "repository": {"owner": "o", "name": "r",
                           "full_name": "o/r", "url": "https://github.com/o/r"},
            "fetched_count": 0, "created_count": 0,
            "updated_count": 0,
            "message": "Insufficient milestone data",
        }

        resp = test_client.post(
            "/api/projects/507f1f77bcf86cd799439022/sync-milestones"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Insufficient milestone data"
        assert data["status"] == "no_milestones"
        self._clear()


# ===========================================================================
# 12. No Unnecessary GitHub Calls Tests
# ===========================================================================

class TestNoUnnecessaryGitHubCalls:
    @patch("Backend.externalservies.github_milestones._fetch_all_milestones")
    @patch("Backend.externalservies.github_milestones.get_project_milestones")
    def test_get_endpoint_never_calls_github(self, mock_db, mock_github):
        mock_db.return_value = []

        get_milestones_for_project("p1")

        mock_github.assert_not_called()


# ===========================================================================
# 13. Network Failure Tests
# ===========================================================================

class TestNetworkFailures:
    @patch("Backend.externalservies.github_milestones._request_milestone_page")
    def test_timeout_raises(self, mock_request):
        mock_request.side_effect = GitHubAPIError("timed out")
        session = MagicMock()
        with pytest.raises(GitHubAPIError, match="timed out"):
            _fetch_milestones_by_state(session, "o", "r", "open")

    @patch("Backend.externalservies.github_milestones._request_milestone_page")
    def test_connection_error_raises(self, mock_request):
        mock_request.side_effect = GitHubAPIError("Could not connect")
        session = MagicMock()
        with pytest.raises(GitHubAPIError, match="connect"):
            _fetch_milestones_by_state(session, "o", "r", "open")


# ===========================================================================
# 14. Security Tests
# ===========================================================================

class TestSecurity:
    def test_no_token_in_error_messages(self):
        resp = MagicMock()
        resp.status_code = 401
        resp.ok = False
        resp.text = "Bad credentials"
        resp.headers = {}

        try:
            _raise_for_milestone_response(resp, "owner", "repo")
        except GitHubAuthError as e:
            msg = str(e)
            assert "ghp_" not in msg
            assert "token" not in msg.lower() or "GITHUB_TOKEN" in msg

    def test_present_milestone_no_internal_fields(self):
        document = {
            "_id": "id1", "projectId": "p1",
            "milestone_id": "1", "title": "Test",
            "description": "", "state": "open",
            "due_on": None, "open_issues": 0,
            "closed_issues": 0, "html_url": "",
            "last_synced_at": "2026-01-01T00:00:00+00:00",
        }
        result = _present_milestone(document)
        assert "last_synced_at" not in result


# ===========================================================================
# 15. Integration Flow Test
# ===========================================================================

class TestIntegrationFlow:
    @patch("Backend.externalservies.github_milestones.upsert_milestone")
    @patch("Backend.externalservies.github_milestones._fetch_all_milestones")
    @patch("Backend.externalservies.github_milestones._get_authenticated_session")
    @patch("Backend.externalservies.github_milestones._parse_github_url")
    @patch("Backend.externalservies.github_milestones._resolve_repo_url")
    @patch("Backend.externalservies.github_milestones.get_project")
    def test_full_sync_flow(
        self, mock_proj, mock_resolve, mock_parse, mock_session,
        mock_fetch, mock_upsert,
    ):
        mock_proj.return_value = {"_id": "p1", "repo_url": "https://github.com/o/r"}
        mock_resolve.return_value = "https://github.com/o/r"
        mock_parse.return_value = ("o", "r")
        mock_session.return_value = MagicMock()

        mock_fetch.return_value = [
            {
                "number": 1, "title": "Sprint 1",
                "description": "First", "state": "open",
                "due_on": "2026-02-01T00:00:00Z",
                "open_issues": 3, "closed_issues": 7,
                "html_url": "https://github.com/o/r/milestone/1",
            },
            {
                "number": 2, "title": "Sprint 2",
                "description": "Second", "state": "closed",
                "due_on": None,
                "open_issues": 0, "closed_issues": 15,
                "html_url": "https://github.com/o/r/milestone/2",
            },
        ]
        mock_upsert.return_value = "inserted_id"

        result = sync_project_milestones("p1")

        assert result["success"] is True
        assert result["fetched_count"] == 2
        assert result["created_count"] == 2
        assert mock_upsert.call_count == 2

        # Verify first milestone was normalized correctly
        first_call = mock_upsert.call_args_list[0][0][1]
        assert first_call["milestone_id"] == "1"
        assert first_call["completion_percentage"] == 70.0

        # Verify second milestone
        second_call = mock_upsert.call_args_list[1][0][1]
        assert second_call["milestone_id"] == "2"
        assert second_call["state"] == "closed"
        assert second_call["completion_percentage"] == 100.0


# ===========================================================================
# 16. Router Registration Test
# ===========================================================================

class TestRouterRegistration:
    def test_milestone_routes_registered(self, test_client):
        """Verify both milestone endpoints exist in the OpenAPI spec."""
        resp = test_client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        paths = spec.get("paths", {})

        # Check GET milestones endpoint
        milestone_get = None
        milestone_post = None
        for path_key, methods in paths.items():
            if "milestones" in path_key and "sync" not in path_key:
                if "get" in methods:
                    milestone_get = methods["get"]
            if "sync-milestones" in path_key:
                if "post" in methods:
                    milestone_post = methods["post"]

        assert milestone_get is not None, \
            "GET /{project_id}/milestones not found in OpenAPI"
        assert milestone_post is not None, \
            "POST /{project_id}/sync-milestones not found in OpenAPI"

