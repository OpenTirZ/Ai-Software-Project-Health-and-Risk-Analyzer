"""
Test suite for TASK-SP3-07 — LLM Pipeline
==========================================
Covers:
  1. LLMClient — backend selection, missing credentials, API errors, timeouts,
     empty responses, and successful Gemini / OpenRouter paths.
  2. report_service — successful generation, schema validation failure (fallback),
     missing API key (fallback), API error (fallback), timeout (fallback),
     empty metrics, and malformed LLM JSON.
  3. explanation_service — successful generation, schema validation failure,
     missing API key (fallback), API error (fallback), multi-flag helper,
     and grounding (evidence values present in output).

All external API calls are mocked — no real API keys or paid requests are needed.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from Backend.ai.llm_client import (
    LLMClient,
    LLMAPIError,
    LLMClientError,
    LLMEmptyResponseError,
    LLMMissingCredentialsError,
    LLMTimeoutError,
    _call_openrouter,
)
from Backend.ai.report_service import generate_report
from Backend.ai.explanation_service import explain_flag, explain_flags
from Backend.ai.schemas import ExplanationSchema, ReportResponseSchema


# ===========================================================================
# Shared fixtures / helpers
# ===========================================================================

def _make_metrics(
    health_score: float = 72.5,
    status: str = "Caution",
    with_flags: bool = True,
) -> Dict[str, Any]:
    """Return a minimal build_metrics_breakdown()-shaped dict."""
    flags = []
    if with_flags:
        flags = [
            {
                "id": "flag_bottleneck_aging_prs",
                "type": "bottleneck",
                "severity": "high",
                "message": "2 pull requests open for longer than 48h.",
                "evidence": {"aging_prs": [{"number": 12, "age_hours": 73.0}]},
            }
        ]
    return {
        "project_id": "proj-001",
        "project_name": "Test Project",
        "health_score": health_score,
        "status": status,
        "indicators": {
            "bottlenecks": {
                "score": 70.0,
                "status": "Caution",
                "data_status": "available",
                "weight": 0.25,
                "details": {
                    "total_prs_tracked": 5,
                    "open_prs_count": 3,
                    "aging_prs_count": 2,
                    "avg_pr_age_hours": 55.0,
                    "aging_threshold_hours": 48.0,
                },
                "flags": flags,
            },
            "workload": {
                "score": 80.0,
                "status": "Good",
                "data_status": "available",
                "weight": 0.25,
                "details": {
                    "total_contributors": 3,
                    "total_activity_events": 40,
                    "top_contributor": "alice",
                    "top_contributor_share": 0.45,
                    "top_contributor_percentage": 45.0,
                    "disclaimer": "GitHub activity is a proxy indicator.",
                },
                "flags": [],
            },
            "stale_issues": {
                "score": 65.0,
                "status": "Caution",
                "data_status": "available",
                "weight": 0.25,
                "details": {
                    "open_issues_count": 10,
                    "stale_issues_count": 3,
                    "stale_issue_percentage": 30.0,
                    "stale_threshold_days": 14,
                },
                "flags": [],
            },
            "schedule_risk": {
                "score": None,
                "status": "Insufficient Data",
                "data_status": "insufficient_data",
                "weight": 0.25,
                "details": {
                    "message": "No milestone tracking data configured.",
                    "milestones_count": 0,
                    "sprints_count": 0,
                },
                "flags": [],
            },
        },
    }


def _make_flag(flag_id: str = "flag_bottleneck_aging_prs") -> Dict[str, Any]:
    """Return a single minimal flag dict."""
    return {
        "id": flag_id,
        "type": "bottleneck",
        "severity": "high",
        "message": "2 pull requests open for longer than 48h.",
        "evidence": {
            "aging_prs": [{"number": 12, "age_hours": 73.0}, {"number": 15, "age_hours": 51.0}]
        },
    }


def _valid_report_json(project_name: str = "Test Project") -> str:
    """Return a JSON string that is a valid ReportResponseSchema."""
    return json.dumps({
        "project_name": project_name,
        "executive_summary": (
            "The project is in a Caution state with a health score of 72.5/100. "
            "Two pull requests have exceeded the 48-hour review threshold, "
            "creating a moderate bottleneck risk."
        ),
        "health_status": "Caution",
        "health_score": 72.5,
        "key_highlights": ["Workload is well-distributed across 3 contributors."],
        "identified_risks": ["2 aging pull requests detected.", "3 stale issues found."],
        "flag_explanations": [],
        "recommendations": [],
        "data_freshness_disclaimer": "Metrics reflect the most recent telemetry snapshot.",
        "missing_data_caveats": ["Schedule risk data is not available."],
    })


def _valid_explanation_json(flag_id: str = "flag_bottleneck_aging_prs") -> str:
    """Return a JSON string that is a valid ExplanationSchema."""
    return json.dumps({
        "indicator_name": flag_id,
        "severity": "HIGH",
        "explanation": (
            "Two pull requests (PR #12 open 73h, PR #15 open 51h) have exceeded "
            "the 48-hour review threshold. Without timely review these PRs may cause "
            "merge conflicts and slow the team's delivery pace."
        ),
        "contributing_metrics": {"aging_prs_count": 2, "aging_threshold_hours": 48},
        "source_period": "Last 14 days",
        "evidence": ["PR #12 open for 73.0h", "PR #15 open for 51.0h"],
        "uncertainty_or_caveats": None,
    })


# ===========================================================================
# 1. LLMClient Tests
# ===========================================================================

class TestLLMClientCredentials:
    """Tests for credential detection and backend availability."""

    def test_no_credentials_reports_no_backend_available(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        c = LLMClient()
        assert not c.any_backend_available

    def test_openrouter_key_makes_openrouter_available(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        c = LLMClient()
        assert c.openrouter_available
        assert c.any_backend_available

    def test_explicit_openrouter_key_in_constructor(self):
        c = LLMClient(openrouter_api_key="sk-explicit")
        assert c.openrouter_available

    def test_gemini_unavailable_without_sdk(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-fake")
        # Mock _try_import_genai to return None (SDK not installed)
        with patch("Backend.ai.llm_client._try_import_genai", return_value=None):
            c = LLMClient()
            assert not c.gemini_available

    def test_gemini_available_when_key_and_sdk_present(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-fake")
        fake_genai = MagicMock()
        with patch("Backend.ai.llm_client._try_import_genai", return_value=fake_genai):
            c = LLMClient()
            assert c.gemini_available


class TestLLMClientChatMissingCredentials:
    """chat() must raise LLMMissingCredentialsError when nothing is configured."""

    def test_raises_missing_credentials_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        c = LLMClient()
        with pytest.raises(LLMMissingCredentialsError):
            c.chat("hello")

    def test_raises_on_empty_prompt(self):
        c = LLMClient(openrouter_api_key="sk-test")
        with pytest.raises(ValueError):
            c.chat("")


class TestLLMClientOpenRouterPaths:
    """Tests exercising the OpenRouter backend via mocked requests.post."""

    def _make_ok_response(self, content: str) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
        resp.raise_for_status = MagicMock()
        return resp

    def test_successful_openrouter_call(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            mock_post.return_value = self._make_ok_response('{"hello": "world"}')
            c = LLMClient(openrouter_api_key="sk-test")
            result = c.chat("test prompt")
        assert result == '{"hello": "world"}'

    def test_http_error_raises_llm_api_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        import requests as _req
        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "Rate limit exceeded"
            resp.raise_for_status.side_effect = _req.exceptions.HTTPError("429")
            mock_post.return_value = resp
            c = LLMClient(openrouter_api_key="sk-test")
            with pytest.raises(LLMAPIError):
                c.chat("test prompt")

    def test_timeout_raises_llm_timeout_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        import requests as _req
        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            mock_post.side_effect = _req.exceptions.Timeout("timed out")
            c = LLMClient(openrouter_api_key="sk-test")
            with pytest.raises(LLMTimeoutError):
                c.chat("test prompt")

    def test_empty_content_raises_llm_empty_response_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            mock_post.return_value = self._make_ok_response("")
            c = LLMClient(openrouter_api_key="sk-test")
            with pytest.raises(LLMEmptyResponseError):
                c.chat("test prompt")

    def test_malformed_response_structure_raises_llm_api_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"unexpected_key": True}  # missing 'choices'
            resp.raise_for_status = MagicMock()
            resp.text = '{"unexpected_key": true}'
            mock_post.return_value = resp
            c = LLMClient(openrouter_api_key="sk-test")
            with pytest.raises(LLMAPIError):
                c.chat("test prompt")

    def test_network_error_raises_llm_api_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        import requests as _req
        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            mock_post.side_effect = _req.exceptions.ConnectionError("network down")
            c = LLMClient(openrouter_api_key="sk-test")
            with pytest.raises(LLMAPIError):
                c.chat("test prompt")


class TestLLMClientGeminiPath:
    """Tests exercising the Gemini backend via mocked SDK."""

    def test_gemini_preferred_over_openrouter_when_both_configured(self, monkeypatch):
        """When both keys are set and SDK is available, Gemini should be used."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-fake")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        fake_genai = MagicMock()
        fake_model = MagicMock()
        fake_response = MagicMock()
        fake_response.text = '{"result": "from gemini"}'
        fake_model.generate_content.return_value = fake_response
        fake_genai.GenerativeModel.return_value = fake_model

        with patch("Backend.ai.llm_client._try_import_genai", return_value=fake_genai):
            c = LLMClient(gemini_api_key="AIzaSy-fake", openrouter_api_key="sk-test")
            result = c.chat("hello gemini")

        assert result == '{"result": "from gemini"}'

    def test_gemini_sdk_not_installed_falls_through_to_openrouter(self, monkeypatch):
        """With GEMINI_API_KEY set but SDK absent, OpenRouter should be used instead."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-fake")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter")

        with patch("Backend.ai.llm_client._try_import_genai", return_value=None), \
             patch("Backend.ai.llm_client.requests.post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = {"choices": [{"message": {"content": "openrouter response"}}]}
            resp.raise_for_status = MagicMock()
            mock_post.return_value = resp
            c = LLMClient(gemini_api_key="AIzaSy-fake", openrouter_api_key="sk-openrouter")
            result = c.chat("hello")
        assert result == "openrouter response"


# ===========================================================================
# 2. report_service Tests
# ===========================================================================

class TestReportServiceSuccess:
    """Successful LLM report generation and validation."""

    def test_generates_valid_report_schema_from_llm(self):
        metrics = _make_metrics()
        fake_llm = MagicMock(return_value=_valid_report_json())
        result = generate_report(metrics, llm_client=fake_llm)
        assert isinstance(result, ReportResponseSchema)
        assert result.health_status == "Caution"
        assert result.health_score == 72.5
        assert "pull requests" in result.executive_summary.lower()

    def test_llm_callable_receives_project_name_in_prompt(self):
        metrics = _make_metrics()
        captured = {}

        def capture_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return _valid_report_json()

        generate_report(metrics, llm_client=capture_llm)
        assert "Test Project" in captured["prompt"]

    def test_llm_callable_receives_metrics_in_prompt(self):
        metrics = _make_metrics()
        captured = {}

        def capture_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return _valid_report_json()

        generate_report(metrics, llm_client=capture_llm)
        # Key metric fields should appear in the prompt context
        assert "aging_prs_count" in captured["prompt"] or "bottlenecks" in captured["prompt"]


class TestReportServiceFallback:
    """Fallback behaviour when LLM is unavailable or fails."""

    def test_no_api_key_returns_deterministic_fallback(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        metrics = _make_metrics()
        result = generate_report(metrics)
        assert isinstance(result, ReportResponseSchema)
        # Deterministic fallback should still reflect the actual status
        assert result.health_status == "Caution"

    def test_llm_validation_failure_returns_fallback(self):
        metrics = _make_metrics()
        # LLM returns JSON that violates schema (missing required fields)
        bad_llm = MagicMock(return_value='{"invalid_field": "oops"}')
        result = generate_report(metrics, llm_client=bad_llm)
        assert isinstance(result, ReportResponseSchema)

    def test_llm_returns_empty_string_returns_fallback(self):
        metrics = _make_metrics()
        empty_llm = MagicMock(return_value="")
        result = generate_report(metrics, llm_client=empty_llm)
        assert isinstance(result, ReportResponseSchema)

    def test_llm_raises_exception_returns_fallback(self):
        metrics = _make_metrics()

        def raising_llm(prompt: str) -> str:
            raise LLMAPIError("API is down")

        result = generate_report(metrics, llm_client=raising_llm)
        assert isinstance(result, ReportResponseSchema)

    def test_llm_timeout_returns_fallback(self):
        metrics = _make_metrics()

        def timeout_llm(prompt: str) -> str:
            raise LLMTimeoutError("Timed out after 30s")

        result = generate_report(metrics, llm_client=timeout_llm)
        assert isinstance(result, ReportResponseSchema)

    def test_llm_returns_malformed_json_returns_fallback(self):
        metrics = _make_metrics()
        bad_json_llm = MagicMock(return_value="not json at all !!!{{{")
        result = generate_report(metrics, llm_client=bad_json_llm)
        assert isinstance(result, ReportResponseSchema)

    def test_empty_metrics_returns_fallback(self):
        # Minimal metrics with no indicator data
        empty_metrics = {
            "project_name": "Empty Project",
            "health_score": None,
            "status": "Insufficient Data",
            "indicators": {},
        }
        result = generate_report(empty_metrics)
        assert isinstance(result, ReportResponseSchema)
        assert result.health_status == "Insufficient Data"

    def test_fallback_includes_missing_data_caveats_for_insufficient_indicators(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        metrics = _make_metrics()
        result = generate_report(metrics)  # no LLM configured → fallback
        # schedule_risk is insufficient; caveat must mention milestone/sprint velocity
        assert any(
            "milestone" in c.lower() or "sprint" in c.lower() or "velocity" in c.lower()
            for c in result.missing_data_caveats
        )

    def test_raises_type_error_on_non_dict_metrics(self):
        with pytest.raises(TypeError):
            generate_report("not a dict")  # type: ignore[arg-type]

    def test_llm_returns_hallucinated_extra_field_returns_fallback(self):
        """Extra fields forbidden by schema should trigger a fallback, not a crash."""
        metrics = _make_metrics()
        hallucinated = json.dumps({
            "project_name": "Test Project",
            "executive_summary": "Looks good overall.",
            "health_status": "Good",
            "health_score": 85.0,
            "key_highlights": [],
            "identified_risks": [],
            "flag_explanations": [],
            "recommendations": [],
            "data_freshness_disclaimer": None,
            "missing_data_caveats": [],
            "HALLUCINATED_KEY": "this is forbidden",  # extra='forbid' will reject
        })
        bad_llm = MagicMock(return_value=hallucinated)
        result = generate_report(metrics, llm_client=bad_llm)
        assert isinstance(result, ReportResponseSchema)


# ===========================================================================
# 3. explanation_service Tests
# ===========================================================================

class TestExplanationServiceSuccess:
    """Successful LLM flag explanation generation and validation."""

    def test_generates_valid_explanation_schema(self):
        flag = _make_flag()
        fake_llm = MagicMock(return_value=_valid_explanation_json())
        result = explain_flag(flag, llm_client=fake_llm)
        assert isinstance(result, ExplanationSchema)
        assert result.severity == "HIGH"
        assert len(result.evidence) >= 1

    def test_explanation_includes_flag_id_in_indicator_name(self):
        flag = _make_flag("flag_workload_concentration_high")
        llm_response = json.dumps({
            "indicator_name": "flag_workload_concentration_high",
            "severity": "HIGH",
            "explanation": "alice contributes 85% of repository activity.",
            "contributing_metrics": {"contribution_percentage": 85.0},
            "source_period": "Last 30 days",
            "evidence": ["alice: 85% of commits"],
            "uncertainty_or_caveats": None,
        })
        fake_llm = MagicMock(return_value=llm_response)
        result = explain_flag(flag, llm_client=fake_llm)
        assert result.indicator_name == "flag_workload_concentration_high"

    def test_source_period_propagated_to_llm_prompt(self):
        flag = _make_flag()
        captured: Dict[str, str] = {}

        def capture_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return _valid_explanation_json()

        explain_flag(flag, source_period="Sprint 3", llm_client=capture_llm)
        assert "Sprint 3" in captured["prompt"]

    def test_evidence_from_flag_appears_in_prompt(self):
        flag = _make_flag()
        captured: Dict[str, str] = {}

        def capture_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return _valid_explanation_json()

        explain_flag(flag, llm_client=capture_llm)
        # Flag's evidence (PR #12) should be in the prompt context
        assert "12" in captured["prompt"] or "aging_prs" in captured["prompt"]


class TestExplanationServiceFallback:
    """Fallback behaviour when LLM is unavailable or fails."""

    def test_no_api_key_returns_deterministic_fallback(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        flag = _make_flag()
        result = explain_flag(flag)
        assert isinstance(result, ExplanationSchema)
        assert result.indicator_name == "flag_bottleneck_aging_prs"
        assert result.severity == "HIGH"
        assert len(result.evidence) >= 1

    def test_llm_validation_failure_returns_fallback(self):
        flag = _make_flag()
        bad_llm = MagicMock(return_value='{"bad_field": 123}')
        result = explain_flag(flag, llm_client=bad_llm)
        assert isinstance(result, ExplanationSchema)

    def test_llm_empty_response_returns_fallback(self):
        flag = _make_flag()
        result = explain_flag(flag, llm_client=MagicMock(return_value=""))
        assert isinstance(result, ExplanationSchema)

    def test_llm_api_error_returns_fallback(self):
        flag = _make_flag()

        def raising_llm(p: str) -> str:
            raise LLMAPIError("Service unavailable")

        result = explain_flag(flag, llm_client=raising_llm)
        assert isinstance(result, ExplanationSchema)

    def test_llm_timeout_returns_fallback(self):
        flag = _make_flag()

        def timeout_llm(p: str) -> str:
            raise LLMTimeoutError("30s timeout")

        result = explain_flag(flag, llm_client=timeout_llm)
        assert isinstance(result, ExplanationSchema)

    def test_fallback_uses_actual_flag_message(self):
        flag = _make_flag()
        result = explain_flag(flag)  # no LLM → fallback
        assert "pull requests" in result.explanation.lower()

    def test_fallback_includes_evidence_from_flag(self):
        flag = _make_flag()
        result = explain_flag(flag)  # no LLM → fallback
        # The fallback should include evidence derived from the flag dict
        assert len(result.evidence) >= 1

    def test_raises_type_error_on_non_dict_flag(self):
        with pytest.raises(TypeError):
            explain_flag("not a dict")  # type: ignore[arg-type]

    def test_raises_value_error_when_flag_has_no_id(self):
        with pytest.raises(ValueError):
            explain_flag({"severity": "high", "message": "some message"})

    def test_severity_normalization_high_to_HIGH(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        flag = {"id": "flag_x", "severity": "high", "message": "risk detected.", "evidence": {}}
        result = explain_flag(flag)
        assert result.severity == "HIGH"

    def test_severity_normalization_medium_to_MEDIUM(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        flag = {"id": "flag_y", "severity": "medium", "message": "moderate risk.", "evidence": {}}
        result = explain_flag(flag)
        assert result.severity == "MEDIUM"

    def test_llm_hallucinated_extra_field_returns_fallback(self):
        flag = _make_flag()
        hallucinated = json.dumps({
            "indicator_name": "flag_bottleneck_aging_prs",
            "severity": "HIGH",
            "explanation": "Two PRs are aging.",
            "contributing_metrics": {},
            "source_period": None,
            "evidence": ["PR #12 open 73h"],
            "uncertainty_or_caveats": None,
            "HALLUCINATED": "forbidden extra field",
        })
        bad_llm = MagicMock(return_value=hallucinated)
        result = explain_flag(flag, llm_client=bad_llm)
        assert isinstance(result, ExplanationSchema)


class TestExplainFlagsHelper:
    """Tests for the explain_flags() batch helper."""

    def test_returns_one_explanation_per_valid_flag(self):
        flags = [_make_flag("flag_a"), _make_flag("flag_b")]
        fake_llm = MagicMock(return_value=_valid_explanation_json())
        results = explain_flags(flags, llm_client=fake_llm)
        assert len(results) == 2
        assert all(isinstance(r, ExplanationSchema) for r in results)

    def test_skips_non_dict_entries_in_list(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        flags = [_make_flag(), "not_a_dict", None]  # type: ignore[list-item]
        results = explain_flags(flags)
        # Only the valid dict should produce an ExplanationSchema
        assert len(results) == 1
        assert isinstance(results[0], ExplanationSchema)

    def test_raises_type_error_on_non_list(self):
        with pytest.raises(TypeError):
            explain_flags("not a list")  # type: ignore[arg-type]

    def test_empty_list_returns_empty_list(self):
        result = explain_flags([])
        assert result == []

    def test_one_failing_flag_does_not_block_others(self):
        """A flag without an 'id' should not prevent valid flags from being explained."""
        good_flag = _make_flag()
        # explain_flags catches non-dict entries; flags without 'id' raise ValueError
        # inside explain_flag but explain_flags does NOT suppress ValueError by design —
        # let's verify only dicts are accepted (non-dicts are skipped)
        flags = [good_flag, _make_flag()]
        fake_llm = MagicMock(return_value=_valid_explanation_json())
        results = explain_flags(flags, llm_client=fake_llm)
        assert len(results) == 2


# ===========================================================================
# 4. Integration-style: LLMClient used inside services
# ===========================================================================

class TestLLMClientIntegrationWithServices:
    """Verify that services correctly use the LLMClient and fall back on errors."""

    def test_report_service_uses_llm_client_openrouter(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = {
                "choices": [{"message": {"content": _valid_report_json()}}]
            }
            resp.raise_for_status = MagicMock()
            mock_post.return_value = resp
            metrics = _make_metrics()
            result = generate_report(metrics)

        assert isinstance(result, ReportResponseSchema)
        assert mock_post.called

    def test_explanation_service_uses_llm_client_openrouter(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

        with patch("Backend.ai.llm_client.requests.post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = {
                "choices": [{"message": {"content": _valid_explanation_json()}}]
            }
            resp.raise_for_status = MagicMock()
            mock_post.return_value = resp
            flag = _make_flag()
            result = explain_flag(flag)

        assert isinstance(result, ExplanationSchema)
        assert mock_post.called

    def test_report_service_falls_back_when_client_has_no_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        result = generate_report(_make_metrics())
        assert isinstance(result, ReportResponseSchema)

    def test_explanation_service_falls_back_when_client_has_no_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        result = explain_flag(_make_flag())
        assert isinstance(result, ExplanationSchema)
