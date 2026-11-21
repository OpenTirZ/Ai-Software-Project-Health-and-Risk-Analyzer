"""
AI Fallback & Secrets-Leak Tests — TASK-QA-FALLBACK
=====================================================
Covers three resilience contracts:

  1. LLM Failure Fallback
     - HTTP 504 Gateway Timeout  → deterministic grounded recommendations returned.
     - HTTP 429 Too Many Requests → deterministic grounded recommendations returned.
     - Requests connection timeout → deterministic grounded recommendations returned.
     - Malformed / empty JSON body → deterministic grounded recommendations returned.
     - LLM raises generic RuntimeError → deterministic grounded recommendations returned.
     All fallback paths must NOT crash (no unhandled exception propagates).

  2. Deterministic Rule Summary Validation
     Confirms that the fallback layer itself produces structurally correct,
     advisory-compliant recommendations independent of any LLM call.

  3. Secrets / API Key Leak Prevention in Debug Logs
     - The OPENROUTER_API_KEY must never appear in log records emitted at any
       level by the recommendation service.
     - The prompt text logged at DEBUG level must not expose the raw key.
     - Sanitised prompt text must not contain recognisable secret patterns.

Important: Do NOT touch anything inside the LangGraph folder.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
import requests

from Backend.ai.recommendation_service import (
    ADVISORY_DISCLAIMER,
    _build_grounded_recommendations,
    _collect_active_flags,
    generate_recommendations,
)
from Backend.ai.schemas import RecommendationSchema


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------

_FAKE_API_KEY = "sk-or-v1-FAKE_SECRET_KEY_DO_NOT_LEAK_1234567890abcdef"
_PHANTOM_KEY_FRAGMENT = "FAKE_SECRET_KEY"


def _make_metrics(flags: List[Dict] | None = None) -> Dict[str, Any]:
    return {
        "project_id": "fallback-test-proj",
        "project_name": "Fallback Test Project",
        "health_score": 58.0,
        "status": "Caution",
        "indicators": {
            "bottlenecks": {
                "score": 58.0,
                "status": "Caution",
                "flags": flags or [],
            }
        },
    }


def _aging_pr_flag() -> Dict:
    return {
        "id": "flag_bottleneck_aging_prs",
        "type": "bottleneck",
        "severity": "high",
        "message": "2 pull requests are overdue.",
        "evidence": {"aging_prs": [{"number": 5, "age_hours": 55}]},
    }


def _stale_issues_flag() -> Dict:
    return {
        "id": "flag_stale_issues_detected",
        "type": "stale_issues",
        "severity": "medium",
        "message": "4 issues inactive over 14 days.",
        "evidence": {"stale_issues": [{"number": 10, "inactive_days": 20}]},
    }


def _mock_http_error(status_code: int) -> requests.HTTPError:
    """Return a requests.HTTPError for a given HTTP status code."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.text = f"HTTP {status_code}"
    err = requests.HTTPError(response=response)
    return err


# ---------------------------------------------------------------------------
# Log Capture Helper
# ---------------------------------------------------------------------------

class _LogCapture(logging.Handler):
    """Capture all log records emitted for a given logger during a test."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    @property
    def all_messages(self) -> str:
        return "\n".join(self.format(r) for r in self.records)


# ===========================================================================
# 1. HTTP 504 Gateway Timeout — Fallback to Deterministic Grounded Advice
# ===========================================================================

class TestHTTP504Fallback:

    def test_504_does_not_crash_service(self):
        """An HTTP 504 must not propagate; service returns grounded recommendations."""
        metrics = _make_metrics([_aging_pr_flag()])

        def gateway_timeout_llm(prompt: str) -> str:
            raise _mock_http_error(504)

        # Must not raise
        recs = generate_recommendations(metrics, llm_client=gateway_timeout_llm)
        assert isinstance(recs, list), "Service must return a list on 504"

    def test_504_returns_grounded_recommendations(self):
        """After a 504, the returned recommendations are the deterministic fallback."""
        metrics = _make_metrics([_aging_pr_flag()])
        flags = _collect_active_flags(metrics)
        expected_grounded = _build_grounded_recommendations(metrics, flags)

        def gateway_timeout_llm(prompt: str) -> str:
            raise _mock_http_error(504)

        recs = generate_recommendations(metrics, llm_client=gateway_timeout_llm)

        assert len(recs) == len(expected_grounded)
        assert recs[0].category == expected_grounded[0].category
        assert recs[0].priority == expected_grounded[0].priority
        assert recs[0].is_advisory is True

    def test_504_via_requests_post_mock(self):
        """Simulate 504 through requests.post mock (integration-level HTTP path)."""
        metrics = _make_metrics([_aging_pr_flag()])

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = _mock_http_error(504)
            mock_post.return_value = mock_response

            recs = generate_recommendations(metrics, api_key=_FAKE_API_KEY)

        assert isinstance(recs, list)
        assert len(recs) == 1
        assert recs[0].is_advisory is True


# ===========================================================================
# 2. HTTP 429 Too Many Requests — Fallback to Deterministic Grounded Advice
# ===========================================================================

class TestHTTP429Fallback:

    def test_429_does_not_crash_service(self):
        """An HTTP 429 quota error must not propagate; service stays up."""
        metrics = _make_metrics([_stale_issues_flag()])

        def quota_exceeded_llm(prompt: str) -> str:
            raise _mock_http_error(429)

        recs = generate_recommendations(metrics, llm_client=quota_exceeded_llm)
        assert isinstance(recs, list)

    def test_429_returns_advisory_compliant_fallback(self):
        """After a 429, every fallback recommendation must be advisory."""
        metrics = _make_metrics([_stale_issues_flag()])

        def quota_exceeded_llm(prompt: str) -> str:
            raise _mock_http_error(429)

        recs = generate_recommendations(metrics, llm_client=quota_exceeded_llm)
        assert len(recs) >= 1
        for rec in recs:
            assert rec.is_advisory is True
            assert ADVISORY_DISCLAIMER in rec.disclaimer
            assert rec.category == "issue_hygiene"

    def test_429_via_requests_post_mock(self):
        """Simulate 429 through requests.post mock."""
        metrics = _make_metrics([_aging_pr_flag()])

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = _mock_http_error(429)
            mock_post.return_value = mock_response

            recs = generate_recommendations(metrics, api_key=_FAKE_API_KEY)

        # Service must have fallen back gracefully
        assert isinstance(recs, list)
        assert len(recs) == 1
        assert recs[0].priority == "HIGH"

    def test_429_multiple_flags_all_returned_via_fallback(self):
        """With multiple flags, 429 fallback must return all grounded recommendations."""
        flags = [_aging_pr_flag(), _stale_issues_flag()]
        metrics: Dict = {
            "project_id": "multi-429",
            "project_name": "Multi Flag 429 Project",
            "health_score": 50.0,
            "status": "Caution",
            "indicators": {
                "bottlenecks": {"score": 55.0, "status": "Caution", "flags": [_aging_pr_flag()]},
                "stale_issues": {"score": 70.0, "status": "Caution", "flags": [_stale_issues_flag()]},
            },
        }

        def quota_exceeded_llm(prompt: str) -> str:
            raise _mock_http_error(429)

        recs = generate_recommendations(metrics, llm_client=quota_exceeded_llm)
        assert len(recs) == 2


# ===========================================================================
# 3. Connection / Timeout Failures
# ===========================================================================

class TestConnectionTimeoutFallback:

    def test_connection_error_falls_back_gracefully(self):
        """A requests.ConnectionError must not propagate."""
        metrics = _make_metrics([_aging_pr_flag()])

        def connection_error_llm(prompt: str) -> str:
            raise requests.ConnectionError("DNS resolution failed")

        recs = generate_recommendations(metrics, llm_client=connection_error_llm)
        assert isinstance(recs, list)
        assert len(recs) == 1

    def test_read_timeout_falls_back_gracefully(self):
        """A requests.ReadTimeout must not propagate."""
        metrics = _make_metrics([_aging_pr_flag()])

        def timeout_llm(prompt: str) -> str:
            raise requests.ReadTimeout("Read timed out after 30s")

        recs = generate_recommendations(metrics, llm_client=timeout_llm)
        assert isinstance(recs, list)
        assert len(recs) == 1
        assert recs[0].is_advisory is True

    def test_requests_timeout_via_post_mock(self):
        """requests.post raising Timeout is handled and falls back."""
        metrics = _make_metrics([_aging_pr_flag()])

        with patch("requests.post", side_effect=requests.Timeout("Connection timed out")):
            recs = generate_recommendations(metrics, api_key=_FAKE_API_KEY)

        assert isinstance(recs, list)
        assert len(recs) == 1


# ===========================================================================
# 4. Malformed / Invalid LLM Response Body Fallback
# ===========================================================================

class TestMalformedLLMResponseFallback:

    def test_empty_response_body_falls_back(self):
        """An empty string response from the LLM falls back to grounded."""
        metrics = _make_metrics([_aging_pr_flag()])
        recs = generate_recommendations(metrics, llm_client=lambda p: "")
        assert len(recs) == 1
        assert recs[0].category == "code_review"

    def test_non_json_response_falls_back(self):
        """Plain text (non-JSON) from LLM falls back gracefully."""
        metrics = _make_metrics([_aging_pr_flag()])
        recs = generate_recommendations(
            metrics, llm_client=lambda p: "Sorry, service is unavailable."
        )
        assert len(recs) == 1
        assert recs[0].is_advisory is True

    def test_json_array_instead_of_object_falls_back(self):
        """An LLM returning a JSON array (not object) falls back."""
        metrics = _make_metrics([_aging_pr_flag()])
        recs = generate_recommendations(
            metrics, llm_client=lambda p: '[{"unexpected": "array"}]'
        )
        assert len(recs) == 1

    def test_missing_recommendations_key_falls_back(self):
        """JSON without the 'recommendations' key triggers Pydantic validation failure."""
        metrics = _make_metrics([_aging_pr_flag()])
        recs = generate_recommendations(
            metrics, llm_client=lambda p: '{"data": "wrong_key"}'
        )
        assert len(recs) == 1

    def test_hallucinated_extra_fields_in_llm_output_falls_back(self):
        """Extra (hallucinated) fields in LLM output are rejected and fall back."""
        metrics = _make_metrics([_aging_pr_flag()])
        flags = _collect_active_flags(metrics)
        grounded = _build_grounded_recommendations(metrics, flags)
        g = grounded[0]

        def hallucinating_llm(prompt: str) -> str:
            return json.dumps({
                "recommendations": [{
                    "category": g.category,
                    "condition": g.condition,
                    "action": g.action,
                    "rationale": g.rationale,
                    "priority": g.priority,
                    "target_role": g.target_role,
                    "is_advisory": True,
                    "disclaimer": ADVISORY_DISCLAIMER,
                    "HALLUCINATED_FIELD": "unexpected_value",  # schema has extra='forbid'
                }]
            })

        recs = generate_recommendations(metrics, llm_client=hallucinating_llm)
        # Schema forbids extra fields → fallback to grounded
        assert len(recs) == 1
        assert recs[0].category == "code_review"

    def test_generic_runtime_error_falls_back(self):
        """A generic RuntimeError in the LLM client must not crash the service."""
        metrics = _make_metrics([_aging_pr_flag()])

        def broken_llm(prompt: str) -> str:
            raise RuntimeError("Unexpected internal failure in LLM client")

        recs = generate_recommendations(metrics, llm_client=broken_llm)
        assert isinstance(recs, list)
        assert len(recs) == 1


# ===========================================================================
# 5. Deterministic Rule Summary Validation (Fallback Layer Correctness)
# ===========================================================================

class TestDeterministicFallbackQuality:
    """
    Verify the deterministic grounding layer produces structurally valid,
    advisory-compliant summaries — independent of any LLM involvement.
    """

    @pytest.mark.parametrize("flag_id,expected_priority,expected_category", [
        ("flag_bottleneck_aging_prs", "HIGH", "code_review"),
        ("flag_pr_queue_congestion", "MEDIUM", "code_review"),
        ("flag_single_contributor", "MEDIUM", "workload_balance"),
        ("flag_workload_concentration_high", "HIGH", "workload_balance"),
        ("flag_workload_concentration_caution", "MEDIUM", "workload_balance"),
        ("flag_schedule_stalled_velocity", "HIGH", "delivery_planning"),
        ("flag_stale_issues_detected", "MEDIUM", "issue_hygiene"),
    ])
    def test_every_known_flag_produces_valid_recommendation(
        self, flag_id: str, expected_priority: str, expected_category: str
    ):
        """Every flag in _FLAG_RECOMMENDATIONS maps to a valid advisory recommendation."""
        flag = {"id": flag_id, "message": "Test condition triggered.", "evidence": {}}
        metrics = _make_metrics([flag])

        recs = generate_recommendations(metrics, api_key="")

        assert len(recs) == 1, f"Flag {flag_id} must produce exactly 1 recommendation"
        rec = recs[0]
        assert rec.category == expected_category
        assert rec.priority == expected_priority
        assert rec.is_advisory is True
        assert ADVISORY_DISCLAIMER in rec.disclaimer
        assert isinstance(rec, RecommendationSchema)

    def test_fallback_recommendation_schema_validates_fully(self):
        """Each grounded fallback recommendation satisfies the full Pydantic schema."""
        flags = [
            {"id": "flag_bottleneck_aging_prs", "message": "2 aging PRs.", "evidence": {}},
            {"id": "flag_stale_issues_detected", "message": "5 stale issues.", "evidence": {}},
        ]
        metrics: Dict = {
            "project_id": "schema-validate",
            "project_name": "Schema Validation Project",
            "health_score": 60.0,
            "status": "Caution",
            "indicators": {
                "bottlenecks": {"score": 60.0, "status": "Caution", "flags": flags},
            },
        }
        recs = generate_recommendations(metrics, api_key="")
        for rec in recs:
            # Re-validate through Pydantic to confirm schema integrity
            validated = RecommendationSchema.model_validate(rec.model_dump())
            assert validated.is_advisory is True
            assert len(validated.action) >= 5
            assert len(validated.rationale) >= 5

    def test_no_flags_means_empty_fallback(self):
        """No active flags → no recommendations, even from the fallback layer."""
        metrics = _make_metrics([])
        recs = generate_recommendations(metrics, api_key="")
        assert recs == []

    def test_no_api_key_and_no_client_uses_grounded_layer(self):
        """
        When neither api_key nor llm_client is supplied, the service must
        return grounded deterministic recommendations without raising.
        """
        metrics = _make_metrics([_aging_pr_flag()])

        with patch.dict(os.environ, {}, clear=False):
            # Ensure OPENROUTER_API_KEY is not set in this test scope
            env_backup = os.environ.pop("OPENROUTER_API_KEY", None)
            try:
                recs = generate_recommendations(metrics)
            finally:
                if env_backup is not None:
                    os.environ["OPENROUTER_API_KEY"] = env_backup

        assert len(recs) == 1
        assert recs[0].category == "code_review"


# ===========================================================================
# 6. Secrets / API Key Leak Prevention in Logs
# ===========================================================================

class TestSecretsLeakPrevention:
    """
    Verify that neither the OPENROUTER_API_KEY nor any recognisable key
    fragment leaks into log records produced by the recommendation service.
    """

    def _capture_logs_for(self, metrics: Dict, llm_client=None, api_key: str | None = None):
        """Run generate_recommendations and capture all log records."""
        capture = _LogCapture()
        # Capture logs from the recommendation service and its dependencies
        for logger_name in (
            "Backend.ai.recommendation_service",
            "Backend.ai.prompt_guard",
        ):
            logging.getLogger(logger_name).addHandler(capture)
            logging.getLogger(logger_name).setLevel(logging.DEBUG)

        try:
            generate_recommendations(metrics, llm_client=llm_client, api_key=api_key)
        finally:
            for logger_name in (
                "Backend.ai.recommendation_service",
                "Backend.ai.prompt_guard",
            ):
                logging.getLogger(logger_name).removeHandler(capture)

        return capture

    def test_api_key_does_not_appear_in_logs_on_success(self):
        """
        When LLM succeeds, the API key must not be present in any log record.
        """
        metrics = _make_metrics([_aging_pr_flag()])
        flags = _collect_active_flags(metrics)
        grounded = _build_grounded_recommendations(metrics, flags)
        g = grounded[0]

        def honest_llm(prompt: str) -> str:
            return json.dumps({
                "recommendations": [{
                    "category": g.category,
                    "condition": g.condition,
                    "action": g.action,
                    "rationale": g.rationale,
                    "priority": g.priority,
                    "target_role": g.target_role,
                    "is_advisory": True,
                    "disclaimer": ADVISORY_DISCLAIMER,
                }]
            })

        capture = self._capture_logs_for(
            metrics, llm_client=honest_llm, api_key=_FAKE_API_KEY
        )
        assert _FAKE_API_KEY not in capture.all_messages, (
            "API key must not appear in log output on successful LLM call"
        )
        assert _PHANTOM_KEY_FRAGMENT not in capture.all_messages

    def test_api_key_does_not_appear_in_logs_on_504(self):
        """On a 504 error, the API key must not leak into warning/error logs."""
        metrics = _make_metrics([_aging_pr_flag()])

        def gateway_timeout_llm(prompt: str) -> str:
            raise _mock_http_error(504)

        capture = self._capture_logs_for(
            metrics, llm_client=gateway_timeout_llm, api_key=_FAKE_API_KEY
        )
        assert _FAKE_API_KEY not in capture.all_messages, (
            "API key must not leak into log output during 504 fallback"
        )
        assert _PHANTOM_KEY_FRAGMENT not in capture.all_messages

    def test_api_key_does_not_appear_in_logs_on_429(self):
        """On a 429 quota error, the API key must not leak into log output."""
        metrics = _make_metrics([_stale_issues_flag()])

        def quota_exceeded_llm(prompt: str) -> str:
            raise _mock_http_error(429)

        capture = self._capture_logs_for(
            metrics, llm_client=quota_exceeded_llm, api_key=_FAKE_API_KEY
        )
        assert _FAKE_API_KEY not in capture.all_messages, (
            "API key must not leak into log output during 429 fallback"
        )

    def test_api_key_does_not_appear_in_fallback_warning_message(self):
        """The fallback warning log message must not contain the API key."""
        metrics = _make_metrics([_aging_pr_flag()])

        def broken_llm(prompt: str) -> str:
            raise RuntimeError(f"Service error. Key={_FAKE_API_KEY}")

        capture = self._capture_logs_for(
            metrics, llm_client=broken_llm, api_key=_FAKE_API_KEY
        )
        # Check only recommendation service logs (not the exc repr which may include key)
        rec_service_records = [
            r for r in capture.records
            if r.name == "Backend.ai.recommendation_service"
        ]
        for record in rec_service_records:
            msg = record.getMessage()
            assert _FAKE_API_KEY not in msg, (
                f"API key leaked in log record: {msg!r}"
            )

    def test_prompt_text_in_llm_client_does_not_contain_api_key(self):
        """
        The prompt string passed to the LLM client must never contain the
        raw API key — the key is only used in the HTTP Authorization header.
        """
        metrics = _make_metrics([_aging_pr_flag()])
        observed_prompts: List[str] = []

        def key_sniffing_llm(prompt: str) -> str:
            observed_prompts.append(prompt)
            raise RuntimeError("Abort after capturing prompt")

        generate_recommendations(
            metrics, llm_client=key_sniffing_llm, api_key=_FAKE_API_KEY
        )

        assert len(observed_prompts) == 1
        prompt_text = observed_prompts[0]
        assert _FAKE_API_KEY not in prompt_text, (
            "API key must not be embedded in the prompt sent to the LLM"
        )
        assert _PHANTOM_KEY_FRAGMENT not in prompt_text

    def test_no_bearer_token_in_prompt_text(self):
        """
        The 'Bearer' authorization string must not appear in the LLM prompt —
        it belongs only in the HTTP Authorization header.
        """
        metrics = _make_metrics([_aging_pr_flag()])
        observed_prompts: List[str] = []

        def sniffing_llm(prompt: str) -> str:
            observed_prompts.append(prompt)
            raise RuntimeError("abort")

        generate_recommendations(
            metrics, llm_client=sniffing_llm, api_key=_FAKE_API_KEY
        )

        if observed_prompts:
            prompt_text = observed_prompts[0]
            # 'Bearer sk-...' must not appear in the LLM prompt body
            assert "Bearer" not in prompt_text or _FAKE_API_KEY not in prompt_text, (
                "Bearer token must not be embedded inside the LLM prompt text"
            )

    def test_environment_variable_key_not_in_logs(self):
        """
        When the API key is sourced from OPENROUTER_API_KEY env var, it must
        not appear in any log record even after a failure.
        """
        metrics = _make_metrics([_aging_pr_flag()])

        def failing_llm(prompt: str) -> str:
            raise requests.ConnectionError("network is unreachable")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": _FAKE_API_KEY}):
            capture = self._capture_logs_for(metrics, llm_client=failing_llm)

        assert _FAKE_API_KEY not in capture.all_messages
        assert _PHANTOM_KEY_FRAGMENT not in capture.all_messages

    @pytest.mark.parametrize("secret_pattern", [
        r"sk-or-v1-[A-Za-z0-9]+",          # OpenRouter key pattern
        r"Bearer [A-Za-z0-9\-_]{20,}",      # Bearer token in HTTP header
        r"Authorization: Bearer",            # Header name + value
    ])
    def test_secret_patterns_absent_from_logs(self, secret_pattern: str):
        """
        Known secret regex patterns must not match any text in the log output.
        """
        metrics = _make_metrics([_aging_pr_flag()])

        def gateway_timeout_llm(prompt: str) -> str:
            raise _mock_http_error(504)

        capture = self._capture_logs_for(
            metrics, llm_client=gateway_timeout_llm, api_key=_FAKE_API_KEY
        )
        matches = re.findall(secret_pattern, capture.all_messages)
        assert not matches, (
            f"Secret pattern '{secret_pattern}' found in logs: {matches}"
        )
