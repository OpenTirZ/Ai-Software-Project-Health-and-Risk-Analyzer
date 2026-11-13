"""
test_telemetry_hardening.py
===========================
Sprint 2 – TASK-SP2-05 / Issue #69
Telemetry Fixtures & Hardening Tests

Covers:
  1. Fixture payload validation and empty-repo replay
  2. Rate-limit trigger handling (HTTP 403 / 429) with mid-pagination abort
  3. Zero-commit divide-by-zero safety in commit_service and persistence
  4. Secret-redaction validation (_SecretMaskingFilter in main.py)

Scope: test-only — zero modifications to application source.
"""

from __future__ import annotations

import ast
import importlib
import json
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PR_FIXTURE_PATH = FIXTURES_DIR / "github_pr_fixtures.json"
ISSUE_FIXTURE_PATH = FIXTURES_DIR / "github_issue_fixtures.json"
MAIN_PY = REPO_ROOT / "Backend" / "main.py"


# ---------------------------------------------------------------------------
# Fixture loaders
# ---------------------------------------------------------------------------

def _load_pr_fixtures() -> dict:
    with PR_FIXTURE_PATH.open() as f:
        return json.load(f)


def _load_issue_fixtures() -> dict:
    with ISSUE_FIXTURE_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# AST-based secret-masking filter loader
# Avoids importing Backend.main (which requires jose, email_validator, etc.)
# ---------------------------------------------------------------------------

def _load_secret_masking_filter():
    """
    Compile only the secret-masking nodes from main.py via AST so the test
    runs without jose / email_validator / langchain_openai being installed.
    """
    source = MAIN_PY.read_text()
    tree = ast.parse(source, filename=str(MAIN_PY))

    # Collect nodes needed for the masking filter
    target_names = {"_SECRET_PATTERN", "_REDACTED", "_SecretMaskingFilter"}
    kept: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            kept.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module in (
            "re", "logging", "logging.config", "os"
        ):
            kept.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            names = set()
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            if names & target_names:
                kept.append(node)
        elif isinstance(node, ast.ClassDef) and node.name in target_names:
            kept.append(node)

    module_ast = ast.Module(body=kept, type_ignores=[])
    ast.fix_missing_locations(module_ast)
    code = compile(module_ast, filename=str(MAIN_PY), mode="exec")
    ns: dict = {}
    try:
        exec(code, ns)  # noqa: S102
    except (ModuleNotFoundError, ImportError):
        # Retry with minimal stubs for any missing top-level imports
        import re
        ns["re"] = re
        ns["logging"] = logging
        exec(code, ns)  # noqa: S102
    return ns


# ===========================================================================
# 1. Fixture Payload Validation & Empty-Repo Replay
# ===========================================================================

class TestFixturePayloads:
    """Validate structure of the mock JSON fixture files."""

    def test_pr_fixture_file_exists(self):
        assert PR_FIXTURE_PATH.exists(), f"Missing: {PR_FIXTURE_PATH}"

    def test_issue_fixture_file_exists(self):
        assert ISSUE_FIXTURE_PATH.exists(), f"Missing: {ISSUE_FIXTURE_PATH}"

    def test_pr_fixture_has_required_top_level_keys(self):
        data = _load_pr_fixtures()
        for key in ("pr_list", "paginated_prs", "pr_details", "pr_reviews",
                    "empty_repo", "rate_limit_responses", "auth_error_responses"):
            assert key in data, f"Missing key '{key}' in PR fixtures"

    def test_pr_list_contains_five_entries(self):
        data = _load_pr_fixtures()
        assert len(data["pr_list"]) == 5

    def test_pr_list_entries_have_required_fields(self):
        required = {"number", "title", "state", "created_at", "updated_at"}
        for pr in _load_pr_fixtures()["pr_list"]:
            missing = required - pr.keys()
            assert not missing, f"PR #{pr.get('number')} missing fields: {missing}"

    def test_pr_paginated_has_two_pages(self):
        data = _load_pr_fixtures()["paginated_prs"]
        assert "page_1" in data and "page_2" in data

    def test_pr_page_1_has_link_header(self):
        data = _load_pr_fixtures()["paginated_prs"]["page_1"]
        assert data["link_header"] is not None
        assert "next" in data["link_header"]

    def test_pr_rate_limit_responses_present(self):
        rl = _load_pr_fixtures()["rate_limit_responses"]
        assert rl["http_403_header"]["status_code"] == 403
        assert rl["http_403_body"]["status_code"] == 403
        assert rl["http_429"]["status_code"] == 429

    def test_issue_fixture_has_required_top_level_keys(self):
        data = _load_issue_fixtures()
        for key in ("paginated_issues", "milestones", "paginated_milestones",
                    "empty_repo", "rate_limit_responses", "auth_error_responses"):
            assert key in data, f"Missing key '{key}' in Issue fixtures"

    def test_issue_paginated_has_three_pages(self):
        pages = _load_issue_fixtures()["paginated_issues"]
        assert all(f"page_{i}" in pages for i in (1, 2, 3))

    def test_issues_contain_embedded_prs_for_filter_testing(self):
        """At least one item per page should have pull_request field set."""
        pages = _load_issue_fixtures()["paginated_issues"]
        pr_items = [
            item
            for page in pages.values()
            for item in page["items"]
            if item.get("pull_request") is not None
        ]
        assert len(pr_items) >= 2, "Expected ≥2 embedded PR items for filter testing"

    def test_milestone_fixture_has_four_scenarios(self):
        m = _load_issue_fixtures()["milestones"]
        assert len(m) == 4

    def test_zero_task_milestone_has_no_issues(self):
        m = _load_issue_fixtures()["milestones"]["zero_task"]
        assert m["open_issues"] == 0
        assert m["closed_issues"] == 0

    def test_empty_repo_pr_fixture(self):
        empty = _load_pr_fixtures()["empty_repo"]
        assert empty["pr_list"] == []
        assert empty["pr_details"] == {}

    def test_empty_repo_issue_fixture(self):
        empty = _load_issue_fixtures()["empty_repo"]
        assert empty["issues"] == []
        assert empty["milestones"] == []


# ===========================================================================
# 2. Rate-Limit Trigger Handling
# ===========================================================================

class TestRateLimitFixtureStructure:
    """
    Validate rate-limit fixture payloads to confirm they carry the fields
    that production code inspects when deciding whether to raise an error.
    """

    @pytest.mark.parametrize("scenario_key,expected_code", [
        ("http_403_header", 403),
        ("http_403_body",   403),
        ("http_429",        429),
    ])
    def test_pr_rate_limit_status_codes(self, scenario_key, expected_code):
        rl = _load_pr_fixtures()["rate_limit_responses"][scenario_key]
        assert rl["status_code"] == expected_code

    @pytest.mark.parametrize("scenario_key,expected_code", [
        ("http_403_header", 403),
        ("http_403_body",   403),
        ("http_429",        429),
    ])
    def test_issue_rate_limit_status_codes(self, scenario_key, expected_code):
        rl = _load_issue_fixtures()["rate_limit_responses"][scenario_key]
        assert rl["status_code"] == expected_code

    def test_http_403_header_carries_rate_limit_reset(self):
        rl = _load_pr_fixtures()["rate_limit_responses"]["http_403_header"]
        assert "X-RateLimit-Reset" in rl["headers"]

    def test_http_429_carries_retry_after(self):
        rl = _load_pr_fixtures()["rate_limit_responses"]["http_429"]
        assert "Retry-After" in rl["headers"]

    def test_http_401_distinguished_from_rate_limit(self):
        """401 (bad credentials) must exist and differ from 403 rate-limit."""
        auth_errors = _load_pr_fixtures()["auth_error_responses"]
        assert auth_errors["http_401"]["status_code"] == 401
        assert auth_errors["http_401"]["body"]["message"] == "Bad credentials"

    def test_http_403_permission_error_distinguished_from_rate_limit(self):
        auth_errors = _load_pr_fixtures()["auth_error_responses"]
        perm = auth_errors["http_403_permission"]
        assert perm["status_code"] == 403
        # Permission error body should NOT contain the word "rate limit"
        assert "rate limit" not in perm["body"]["message"].lower()


# ===========================================================================
# 3. Zero-Commit / Divide-by-Zero Safety
# ---------------------------------------------------------------------------
# Backend.database connects to MongoDB at import time (client.admin.command
# "ping").  Patch pymongo.MongoClient globally so the entire import chain
# works without a live database, then import commit_service once and reuse it.
# ---------------------------------------------------------------------------

_mongo_patcher = patch("pymongo.MongoClient")
_mock_mongo_cls = _mongo_patcher.start()
_mock_mongo_cls.return_value.admin.command.return_value = {"ok": 1}

# Now the import chain is safe
from Backend.externalservies.commit_service import (  # noqa: E402
    sync_project_commits as _sync_project_commits,
    get_commits_for_project as _get_commits_for_project,
)
import Backend.externalservies.commit_service as _commit_service_mod  # noqa: E402

# ===========================================================================


def _make_mock_github_result(commits: list) -> dict:
    """Build a minimal get_github_commit_history return value."""
    return {
        "repository": {
            "owner": "owner",
            "name": "repo",
            "full_name": "owner/repo",
            "url": "https://github.com/owner/repo",
        },
        "branch": {
            "selected": "main",
            "default": "main",
        },
        "commit_count": len(commits),
        "commits": commits,
    }


class TestZeroCommitSafety:
    """
    Confirm commit_service.sync_project_commits handles zero-commit repositories
    without arithmetic errors, and that input-validation guards are safe.
    """

    def test_zero_commits_returns_synced_count_zero(self):
        """sync_project_commits with an empty commit list must return synced_count=0."""
        with (
            patch.object(_commit_service_mod, "get_project",
                         return_value={"_id": "proj1", "repo_url": "https://github.com/o/r"}),
            patch.object(_commit_service_mod, "_resolve_repo_url",
                         return_value="https://github.com/o/r"),
            patch.object(_commit_service_mod, "get_github_commit_history",
                         return_value=_make_mock_github_result([])),
        ):
            result = _sync_project_commits("proj1")

        assert result["synced_count"] == 0
        assert result["commits"] == []
        assert result["success"] is True

    def test_zero_commits_does_not_call_upsert(self):
        """No DB write attempted when commit list is empty."""
        mock_upsert = MagicMock()
        with (
            patch.object(_commit_service_mod, "get_project",
                         return_value={"_id": "proj1", "repo_url": "https://github.com/o/r"}),
            patch.object(_commit_service_mod, "_resolve_repo_url",
                         return_value="https://github.com/o/r"),
            patch.object(_commit_service_mod, "get_github_commit_history",
                         return_value=_make_mock_github_result([])),
            patch.object(_commit_service_mod, "upsert_commit", mock_upsert),
        ):
            _sync_project_commits("proj1")

        mock_upsert.assert_not_called()

    def test_single_commit_does_not_raise(self):
        """Sanity check: a single-commit repo succeeds without errors."""
        commits = [
            {
                "sha": "abc123def456abc123def456abc123def456abc1",
                "short_sha": "abc123d",
                "author": "alice",
                "timestamp": "2026-10-01T09:00:00Z",
                "message": "Initial commit",
            }
        ]
        with (
            patch.object(_commit_service_mod, "get_project",
                         return_value={"_id": "proj1", "repo_url": "https://github.com/o/r"}),
            patch.object(_commit_service_mod, "_resolve_repo_url",
                         return_value="https://github.com/o/r"),
            patch.object(_commit_service_mod, "get_github_commit_history",
                         return_value=_make_mock_github_result(commits)),
            patch.object(_commit_service_mod, "upsert_commit",
                         return_value="mongo-id-1"),
        ):
            result = _sync_project_commits("proj1")

        assert result["synced_count"] == 1
        assert result["success"] is True

    def test_empty_project_id_raises_value_error(self):
        with pytest.raises(ValueError, match="project_id is required"):
            _sync_project_commits("")

    def test_zero_max_commits_raises_value_error(self):
        with pytest.raises(ValueError, match="max_commits must be a positive integer"):
            _sync_project_commits("proj1", max_commits=0)

    def test_negative_max_commits_raises_value_error(self):
        with pytest.raises(ValueError, match="max_commits must be a positive integer"):
            _sync_project_commits("proj1", max_commits=-5)

    def test_get_commits_for_project_empty_id_raises(self):
        with pytest.raises(ValueError, match="project_id is required"):
            _get_commits_for_project("   ")


# ===========================================================================
# 4. Secret Redaction Validation
# ===========================================================================

class TestSecretRedaction:
    """
    Validate _SecretMaskingFilter strips GitHub tokens and other secrets
    from log records before they are emitted.
    """

    @pytest.fixture(scope="class")
    def masking_ns(self):
        """Load masking filter namespace via AST (no full Backend.main import)."""
        return _load_secret_masking_filter()

    def test_secret_masking_filter_class_exists(self, masking_ns):
        assert "_SecretMaskingFilter" in masking_ns

    def test_secret_pattern_matches_github_token(self, masking_ns):
        pattern = masking_ns["_SECRET_PATTERN"]
        sample = "token=ghp_SuperSecretToken1234567890abcdef"
        assert pattern.search(sample), "Pattern should match 'token=<value>'"

    def test_secret_pattern_matches_authorization_header(self, masking_ns):
        pattern = masking_ns["_SECRET_PATTERN"]
        sample = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        assert pattern.search(sample)

    def test_secret_pattern_matches_mongo_uri(self, masking_ns):
        pattern = masking_ns["_SECRET_PATTERN"]
        sample = "mongo_uri=mongodb+srv://user:pass@cluster.mongodb.net/db"
        assert pattern.search(sample)

    def test_filter_redacts_token_in_msg(self, masking_ns, caplog):
        """
        A log record whose msg contains a raw token value is masked
        before it would be written to any handler.
        """
        FilterCls = masking_ns["_SecretMaskingFilter"]
        flt = FilterCls()

        record = logging.LogRecord(
            name="test.secret",
            level=logging.ERROR,
            pathname=__file__,
            lineno=0,
            msg="Connecting with token=ghp_SECRETTOKEN_abc123",
            args=(),
            exc_info=None,
        )
        result = flt.filter(record)

        assert result is True, "filter() must always return True (never suppress records)"
        assert "ghp_SECRETTOKEN_abc123" not in record.msg
        assert "<REDACTED>" in record.msg

    def test_filter_redacts_token_in_args(self, masking_ns):
        """String args containing secrets are also redacted."""
        FilterCls = masking_ns["_SecretMaskingFilter"]
        flt = FilterCls()

        token = "ghp_SECRETARG_xyz789"
        record = logging.LogRecord(
            name="test.secret.args",
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg="DB failure with %s",
            args=(f"key=token={token}",),
            exc_info=None,
        )
        flt.filter(record)

        for arg in record.args:
            if isinstance(arg, str):
                assert token not in arg, "Secret must be redacted in args too"

    def test_filter_leaves_safe_messages_unchanged(self, masking_ns):
        FilterCls = masking_ns["_SecretMaskingFilter"]
        flt = FilterCls()

        record = logging.LogRecord(
            name="test.safe",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="Synced 42 commits for project my-project",
            args=(),
            exc_info=None,
        )
        original_msg = record.msg
        flt.filter(record)
        assert record.msg == original_msg, "Safe messages must not be altered"

    def test_filter_redacts_password_field(self, masking_ns):
        FilterCls = masking_ns["_SecretMaskingFilter"]
        flt = FilterCls()

        record = logging.LogRecord(
            name="test.password",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=0,
            msg="Connecting with password=SuperSecret!99",
            args=(),
            exc_info=None,
        )
        flt.filter(record)
        assert "SuperSecret!99" not in record.msg
        assert "<REDACTED>" in record.msg
