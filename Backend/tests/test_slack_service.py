"""
Automated Test Suite for Slack Delivery Service (TASK-SP3-08 / Issue #82)
--------------------------------------------------------------------------
Comprehensive unit and integration tests covering:
1. Block Kit payload formatting (valid, missing fields, nulls, risk highlighting, buttons).
2. Webhook URL validation (HTTPS, missing, empty, malformed, unsupported schemes).
3. HTTP delivery and error handling (200 OK, 429 rate limit + Retry-After, 400, 403, 500, timeouts, connection errors).
4. Security and secret token redaction in logs and exception messages.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from Backend.externalservies.slack_service import (
    DEFAULT_APP_BASE_URL,
    DEFAULT_SLACK_TIMEOUT,
    SLACK_WEBHOOK_URL_ENV,
    SlackDeliveryError,
    SlackDeliveryResult,
    SlackIntegrationError,
    SlackRateLimitError,
    SlackWebhookUrlError,
    _extract_health_score,
    _extract_project_info,
    _extract_recommendations,
    _extract_risks,
    _extract_summary,
    _resolve_report_url,
    build_slack_payload,
    format_slack_report_blocks,
    mask_webhook_url,
    post_to_slack_webhook,
    send_slack_report,
    validate_webhook_url,
)

SAMPLE_SECRET_TOKEN = "SUPER_SECRET_SLACK_TOKEN_VALUE_123456789"
VALID_WEBHOOK_URL = f"https://hooks.slack.com/services/T12345678/B87654321/{SAMPLE_SECRET_TOKEN}"


@pytest.fixture(autouse=True)
def _prevent_real_network_calls(monkeypatch):
    """Safety guard: prevent any automated test from executing a real network request."""
    def _fail_on_network(*args, **kwargs):
        raise AssertionError("Real network access attempted during Slack service tests!")

    # By default, monkeypatch requests.post; tests that mock HTTP will override this
    monkeypatch.setattr(requests, "post", _fail_on_network)


def make_sample_report(
    score: int = 85,
    status: str = "healthy",
    high_risks: int = 1,
    medium_risks: int = 1,
) -> dict:
    """Generate a realistic complete status report dictionary."""
    risks = []
    for i in range(high_risks):
        risks.append({
            "risk_id": f"high_risk_{i+1}",
            "severity": "high",
            "evidence": f"High risk evidence description number {i+1}.",
            "recommendation": f"Action for high risk {i+1}.",
        })
    for i in range(medium_risks):
        risks.append({
            "risk_id": f"medium_risk_{i+1}",
            "severity": "medium",
            "evidence": f"Medium risk evidence description number {i+1}.",
            "recommendation": f"Action for medium risk {i+1}.",
        })

    return {
        "project_name": "Aegis AI Project",
        "project_id": "proj_aegis_12345",
        "report_id": "rep_98765",
        "generated_at": "2026-11-19T12:00:00Z",
        "executive_summary": "Overall project health is strong with active pull request cadence.",
        "project_health": {
            "score": score,
            "status": status,
            "confidence": "high",
            "coverage_ratio": 1.0,
            "risk_factors": risks,
        },
        "recommendations": [
            "Review unassigned backlog items.",
            "Schedule upcoming sprint milestone.",
        ],
    }


# ===========================================================================
# 1. Payload Formatting Tests
# ===========================================================================

class TestPayloadFormatting:
    def test_valid_complete_report(self):
        """Complete report generates valid Block Kit blocks with prominent score, button, and risks."""
        report = make_sample_report(score=82, status="healthy", high_risks=1, medium_risks=1)
        blocks = format_slack_report_blocks(report, report_url="https://app.example.com/reports/1")

        assert isinstance(blocks, list)
        assert len(blocks) >= 5

        # 1. Header block
        header = blocks[0]
        assert header["type"] == "header"
        assert "Aegis AI Project" in header["text"]["text"]

        # 2. Score section with interactive button accessory
        score_section = blocks[1]
        assert score_section["type"] == "section"
        assert "82/100" in score_section["text"]["text"]
        assert "🟢 *HEALTHY*" in score_section["text"]["text"]
        assert "accessory" in score_section
        button = score_section["accessory"]
        assert button["type"] == "button"
        assert button["url"] == "https://app.example.com/reports/1"
        assert button["style"] == "primary"

        # 3. Risk callouts
        risk_blocks = [b for b in blocks if "High-Priority" in b.get("text", {}).get("text", "")]
        assert len(risk_blocks) == 1
        assert "🚨" in risk_blocks[0]["text"]["text"]

        # 4. Payload wrapper
        payload = build_slack_payload(report)
        assert "text" in payload
        assert "blocks" in payload
        assert "82/100" in payload["text"]

    def test_missing_project_name(self):
        """Report without project name uses sensible default or explicit parameter."""
        report = make_sample_report()
        del report["project_name"]
        del report["project_id"]

        # Default fallback
        blocks = format_slack_report_blocks(report)
        assert "Software Project" in blocks[0]["text"]["text"]

        # Explicit parameter override
        blocks_explicit = format_slack_report_blocks(report, project_name="Custom Repo Name")
        assert "Custom Repo Name" in blocks_explicit[0]["text"]["text"]

    def test_missing_health_score(self):
        """Missing or null health score displays N/A and unassessed status."""
        report = make_sample_report()
        report["project_health"]["score"] = None
        report["project_health"]["status"] = "not_assessed"

        blocks = format_slack_report_blocks(report)
        score_text = blocks[1]["text"]["text"]
        assert "N/A" in score_text
        assert "⚪ *NOT ASSESSED*" in score_text

        # Button should not have a danger or primary style for unassessed
        button = blocks[1]["accessory"]
        assert "style" not in button or button.get("style") is None

    def test_null_or_empty_risk_list(self):
        """Null or empty risks list renders clean 'No active risks detected' message."""
        # Empty list
        report_empty = make_sample_report(high_risks=0, medium_risks=0)
        blocks_empty = format_slack_report_blocks(report_empty)
        assert any("No active project risks detected" in b.get("text", {}).get("text", "") for b in blocks_empty)

        # None/null risks
        report_null = make_sample_report()
        report_null["project_health"]["risk_factors"] = None
        blocks_null = format_slack_report_blocks(report_null)
        assert any("No active project risks detected" in b.get("text", {}).get("text", "") for b in blocks_null)

    def test_multiple_risks_high_priority_highlighted(self):
        """High priority risks are grouped and highlighted distinctly from medium/low risks."""
        report = make_sample_report(score=42, status="at_risk", high_risks=2, medium_risks=3)
        blocks = format_slack_report_blocks(report)

        # Score < 50 button style should be "danger"
        button = blocks[1]["accessory"]
        assert button.get("style") == "danger"
        assert "🔴 *AT RISK*" in blocks[1]["text"]["text"]

        # High priority block
        high_block = next(b for b in blocks if "High-Priority" in b.get("text", {}).get("text", ""))
        assert "High Risk 1" in high_block["text"]["text"]
        assert "High Risk 2" in high_block["text"]["text"]

        # Other active risks block
        other_block = next(b for b in blocks if "Other Active Risk" in b.get("text", {}).get("text", ""))
        assert "Medium Risk 1" in other_block["text"]["text"]

    def test_missing_optional_fields(self):
        """Empty report dictionary produces valid Block Kit blocks without raising exceptions."""
        empty_report = {}
        blocks = format_slack_report_blocks(empty_report)
        assert isinstance(blocks, list)
        assert len(blocks) >= 3
        payload = build_slack_payload(empty_report)
        assert isinstance(payload["text"], str)
        assert isinstance(payload["blocks"], list)

    def test_correct_slack_block_kit_structure(self):
        """All emitted blocks conform strictly to Slack Block Kit JSON specifications."""
        report = make_sample_report()
        blocks = format_slack_report_blocks(report)

        allowed_block_types = {"header", "section", "divider", "actions", "context"}
        for b in blocks:
            assert b["type"] in allowed_block_types
            if "text" in b:
                assert "type" in b["text"]
                assert b["text"]["type"] in ("plain_text", "mrkdwn")
                assert "text" in b["text"]

    def test_valid_button_action_structure(self):
        """Interactive button in Block Kit contains valid plain_text label and HTTP/HTTPS destination URL."""
        report = make_sample_report()

        # 1. Explicit report_url argument
        blocks1 = format_slack_report_blocks(report, report_url="https://dashboard.example.com/proj/1")
        assert blocks1[1]["accessory"]["url"] == "https://dashboard.example.com/proj/1"

        # 2. Derived from project_id & report_id
        blocks2 = format_slack_report_blocks(report)
        expected_dest = f"{DEFAULT_APP_BASE_URL}/projects/{report['project_id']}/reports/{report['report_id']}"
        assert blocks2[1]["accessory"]["url"] == expected_dest

        # 3. Button plain_text configuration
        button = blocks2[1]["accessory"]
        assert button["type"] == "button"
        assert button["text"]["type"] == "plain_text"
        assert button["text"]["emoji"] is True

    def test_special_characters_and_long_text_handling(self):
        """Handles special characters (&, <, >) and truncates long strings to Slack limits."""
        long_summary = "A" * 2500
        long_title = "Special <Project> & Title " + ("X" * 200)
        report = {
            "project_name": long_title,
            "executive_summary": long_summary,
            "project_health": {"score": 75, "status": "healthy"},
            "recommendations": ["A" * 300],
        }
        blocks = format_slack_report_blocks(report)

        # Header must not exceed 150 characters
        assert len(blocks[0]["text"]["text"]) <= 150
        # Section text must be bounded
        assert len(blocks[2]["text"]["text"]) <= 3000

    def test_various_report_payload_shapes(self):
        """Supports pipeline_v2 shape, MongoDB persistence shape, and API router response shape."""
        # Shape A: pipeline_v2 direct output
        shape_a = {
            "project_health": {"score": 90, "status": "healthy"},
            "executive_summary": "Pipeline V2 output",
        }
        b_a = format_slack_report_blocks(shape_a)
        assert "90/100" in b_a[1]["text"]["text"]

        # Shape B: MongoDB persistence shape
        shape_b = {
            "projectId": "mongo_proj_1",
            "summary": "Mongo persisted summary",
            "metricsSnapshot": {
                "project_health": {"score": 65, "status": "needs_attention"}
            },
        }
        b_b = format_slack_report_blocks(shape_b)
        assert "65/100" in b_b[1]["text"]["text"]

        # Shape C: Router response shape
        shape_c = {
            "success": True,
            "health_score": 55,
            "health_status": "needs_attention",
            "report": {
                "executive_summary": "Router report",
            },
        }
        b_c = format_slack_report_blocks(shape_c)
        assert "55/100" in b_c[1]["text"]["text"]


# ===========================================================================
# 2. Webhook Validation Tests
# ===========================================================================

class TestWebhookValidation:
    def test_valid_https_webhook_url(self):
        """Valid Slack HTTPS webhook URL passes validation."""
        valid_url = "https://hooks.slack.com/services/T00/B00/X00"
        result = validate_webhook_url(valid_url)
        assert result == valid_url

    def test_missing_webhook_url(self):
        """None or non-string webhook URL raises SlackWebhookUrlError."""
        with pytest.raises(SlackWebhookUrlError, match="must not be None"):
            validate_webhook_url(None)

        with pytest.raises(SlackWebhookUrlError, match="must be a string"):
            validate_webhook_url(12345)  # type: ignore

    def test_empty_url(self):
        """Empty or whitespace-only webhook URL raises SlackWebhookUrlError."""
        with pytest.raises(SlackWebhookUrlError, match="must not be empty"):
            validate_webhook_url("")

        with pytest.raises(SlackWebhookUrlError, match="must not be empty"):
            validate_webhook_url("   \t\n")

    def test_unsupported_scheme(self):
        """Non-HTTPS schemes (http, ftp) are rejected with clear error."""
        with pytest.raises(SlackWebhookUrlError, match="must use HTTPS"):
            validate_webhook_url("http://hooks.slack.com/services/T00/B00/X00")

        with pytest.raises(SlackWebhookUrlError, match="must use HTTPS"):
            validate_webhook_url("ftp://hooks.slack.com/services/T00/B00/X00")

    def test_malformed_url(self):
        """Malformed URLs (missing host, missing path, or invalid characters) are rejected."""
        # Missing host
        with pytest.raises(SlackWebhookUrlError, match="missing hostname"):
            validate_webhook_url("https:///services/T0/B0/X0")

        # Missing path
        with pytest.raises(SlackWebhookUrlError, match="missing webhook path"):
            validate_webhook_url("https://hooks.slack.com")

        with pytest.raises(SlackWebhookUrlError, match="missing webhook path"):
            validate_webhook_url("https://hooks.slack.com/")

        # Invalid hostname spaces
        with pytest.raises(SlackWebhookUrlError, match="invalid hostname"):
            validate_webhook_url("https://hooks slack com/services/T0/B0/X0")


# ===========================================================================
# 3. HTTP Delivery & Error Handling Tests
# ===========================================================================

class TestHttpDelivery:
    def test_successful_slack_response(self, monkeypatch):
        """HTTP 200 with 'ok' response returns successful delivery result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        payload = {"text": "Test"}
        result = post_to_slack_webhook(VALID_WEBHOOK_URL, payload)

        assert result.success is True
        assert result.status_code == 200
        assert result.response_body == "ok"
        assert result.error is None

    def test_http_429_rate_limit(self, monkeypatch):
        """HTTP 429 response detects rate limit and parses Retry-After header."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate_limited"
        mock_response.headers = {"Retry-After": "30"}

        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        payload = {"text": "Test"}

        # 1. Result return mode (raise_on_error=False)
        result = post_to_slack_webhook(VALID_WEBHOOK_URL, payload, raise_on_error=False)
        assert result.success is False
        assert result.status_code == 429
        assert result.retry_after == 30
        assert "30s" in (result.error or "")

        # 2. Exception raising mode (raise_on_error=True)
        with pytest.raises(SlackRateLimitError) as exc_info:
            post_to_slack_webhook(VALID_WEBHOOK_URL, payload, raise_on_error=True)
        assert exc_info.value.retry_after == 30
        assert exc_info.value.status_code == 429

    def test_http_400_response(self, monkeypatch):
        """HTTP 400 Bad Request records failure with response body detail."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_payload"

        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        result = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert result.success is False
        assert result.status_code == 400
        assert "invalid_payload" in (result.error or "")

        with pytest.raises(SlackDeliveryError) as exc_info:
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)
        assert exc_info.value.status_code == 400

    def test_http_403_response(self, monkeypatch):
        """HTTP 403 Forbidden indicates token revoked or action prohibited."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "action_prohibited"

        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        result = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert result.success is False
        assert result.status_code == 403
        assert "action_prohibited" in (result.error or "")

    def test_http_500_response(self, monkeypatch):
        """HTTP 500 response captures Slack server failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "internal_error"

        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        result = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert result.success is False
        assert result.status_code == 500

    def test_network_timeout(self, monkeypatch):
        """Network timeout is handled cleanly without raising uncaught exception."""
        def _timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("Read timeout after 10.0s")

        monkeypatch.setattr(requests, "post", _timeout)

        result = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, timeout=5.0, raise_on_error=False)
        assert result.success is False
        assert "timed out after 5.0 seconds" in (result.error or "")

        with pytest.raises(SlackDeliveryError, match="timed out"):
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, timeout=5.0, raise_on_error=True)

    def test_connection_error(self, monkeypatch):
        """Connection failure is caught and formatted into clear error."""
        def _conn_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError("Name resolution failed")

        monkeypatch.setattr(requests, "post", _conn_error)

        result = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert result.success is False
        assert "connection" in (result.error or "").lower()

        with pytest.raises(SlackDeliveryError, match="connection"):
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)

    def test_unexpected_exception(self, monkeypatch):
        """Unexpected runtime errors are captured into SlackDeliveryError."""
        def _boom(*args, **kwargs):
            raise RuntimeError("Unexpected memory fault")

        monkeypatch.setattr(requests, "post", _boom)

        result = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert result.success is False
        assert "Unexpected error" in (result.error or "")

    def test_send_slack_report_integration(self, monkeypatch):
        """send_slack_report combines formatting and delivery in one call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        called_payloads = []

        def _capture_post(url, json, headers, timeout):
            called_payloads.append(json)
            return mock_response

        monkeypatch.setattr(requests, "post", _capture_post)

        report = make_sample_report(score=77)
        result = send_slack_report(
            report_data=report,
            webhook_url=VALID_WEBHOOK_URL,
            project_name="Aegis",
        )

        assert result.success is True
        assert len(called_payloads) == 1
        assert "77/100" in called_payloads[0]["text"]
        assert "Aegis" in called_payloads[0]["text"]

    def test_send_slack_report_env_var_fallback(self, monkeypatch):
        """send_slack_report reads SLACK_WEBHOOK_URL environment variable when url is omitted."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        monkeypatch.setenv(SLACK_WEBHOOK_URL_ENV, VALID_WEBHOOK_URL)
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        report = make_sample_report()
        result = send_slack_report(report_data=report)
        assert result.success is True

    def test_send_slack_report_missing_url_and_env(self, monkeypatch):
        """send_slack_report returns clear error when neither parameter nor env var is provided."""
        monkeypatch.delenv(SLACK_WEBHOOK_URL_ENV, raising=False)
        report = make_sample_report()

        result = send_slack_report(report_data=report)
        assert result.success is False
        assert "SLACK_WEBHOOK_URL" in (result.error or "")

        with pytest.raises(SlackWebhookUrlError, match="SLACK_WEBHOOK_URL"):
            send_slack_report(report_data=report, raise_on_error=True)


# ===========================================================================
# 4. Security & Redaction Tests
# ===========================================================================

class TestSecurityAndRedaction:
    def test_webhook_token_not_exposed_in_logs(self, caplog, monkeypatch):
        """Secret webhook token is never logged in info, warning, or error logs."""
        caplog.set_level(logging.DEBUG)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate_limited"
        mock_response.headers = {"Retry-After": "15"}

        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "security_test"}, raise_on_error=False)

        captured_text = caplog.text
        # Secret token must NOT be present in any log record
        assert SAMPLE_SECRET_TOKEN not in captured_text
        # Masked representation should be logged
        assert "<REDACTED>" in captured_text

    def test_webhook_token_not_exposed_in_exceptions(self, monkeypatch):
        """Secret webhook token is never exposed in raised exception messages."""
        # 1. SlackRateLimitError
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.text = "rate_limited"
        mock_429.headers = {"Retry-After": "5"}
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_429)

        with pytest.raises(SlackRateLimitError) as exc_429:
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)
        assert SAMPLE_SECRET_TOKEN not in str(exc_429.value)

        # 2. SlackDeliveryError (HTTP 500)
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.text = "internal_error"
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_500)

        with pytest.raises(SlackDeliveryError) as exc_500:
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)
        assert SAMPLE_SECRET_TOKEN not in str(exc_500.value)
        assert "<REDACTED>" in str(exc_500.value)

        # 3. Timeout error
        def _timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("Timeout")
        monkeypatch.setattr(requests, "post", _timeout)

        with pytest.raises(SlackDeliveryError) as exc_timeout:
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)
        assert SAMPLE_SECRET_TOKEN not in str(exc_timeout.value)

    def test_mask_webhook_url_helper(self):
        """mask_webhook_url conceals sensitive token segments across various URL structures."""
        # Standard Slack webhook URL
        masked = mask_webhook_url("https://hooks.slack.com/services/T12345/B67890/SECRET123456789")
        assert "SECRET123456789" not in masked
        assert masked == "https://hooks.slack.com/services/T12.../B67.../<REDACTED>"

        # Empty / None
        assert mask_webhook_url(None) == "<empty>"
        assert mask_webhook_url("") == "<empty>"

        # Generic URL with token
        generic_masked = mask_webhook_url("https://custom.webhook.site/webhook/SUPER_TOKEN")
        assert "SUPER_TOKEN" not in generic_masked
        assert "<REDACTED>" in generic_masked


# ===========================================================================
# 5. Block Kit Formatting Edge Cases & Boundary Tests
# ===========================================================================

class TestBlockKitFormattingEdgeCases:
    def test_non_dict_report_input(self):
        """Non-dict report inputs (None, list, string) are handled gracefully."""
        blocks_none = format_slack_report_blocks(None)  # type: ignore
        assert isinstance(blocks_none, list)
        assert len(blocks_none) >= 3

        blocks_list = format_slack_report_blocks(["invalid", "payload"])  # type: ignore
        assert isinstance(blocks_list, list)
        assert len(blocks_list) >= 3

        payload = build_slack_payload(None)  # type: ignore
        assert "Project Health Report" in payload["text"]

    def test_score_ranges_and_boundaries(self):
        """Evaluates boundary scores: negative, zero, 49, 50, 74, 75, >100, float, and non-numeric strings."""
        test_cases = [
            (-10, "🔴 *AT RISK*", "danger", "-10/100"),
            (0, "🔴 *AT RISK*", "danger", "0/100"),
            (49, "🔴 *AT RISK*", "danger", "49/100"),
            (50, "🟡 *NEEDS ATTENTION*", None, "50/100"),
            (74, "🟡 *NEEDS ATTENTION*", None, "74/100"),
            (75, "🟢 *HEALTHY*", "primary", "75/100"),
            (100, "🟢 *HEALTHY*", "primary", "100/100"),
            (120, "🟢 *HEALTHY*", "primary", "120/100"),
            (87.6, "🟢 *HEALTHY*", "primary", "88/100"),
        ]
        for score_val, expected_badge, expected_style, expected_display in test_cases:
            report = {"project_health": {"score": score_val}}
            blocks = format_slack_report_blocks(report)
            score_text = blocks[1]["text"]["text"]
            assert expected_badge in score_text
            assert expected_display in score_text
            button = blocks[1]["accessory"]
            assert button.get("style") == expected_style

        # Non-numeric score string
        non_numeric_report = {"project_health": {"score": "not_a_number"}}
        blocks_nn = format_slack_report_blocks(non_numeric_report)
        assert "⚪ *NOT ASSESSED*" in blocks_nn[1]["text"]["text"]
        assert "N/A" in blocks_nn[1]["text"]["text"]

    def test_risks_without_evidence(self):
        """Risks with empty evidence strings are formatted without evidence snippet."""
        report = {
            "risks": [
                {"risk_id": "critical_cve", "severity": "high", "evidence": ""},
                {"risk_id": "stale_branch", "severity": "medium", "evidence": ""},
            ]
        }
        blocks = format_slack_report_blocks(report)
        text_content = "\n".join(b.get("text", {}).get("text", "") for b in blocks)
        assert "• 🚨 *Critical Cve* (HIGH)" in text_content
        assert "• ⚠️ *Stale Branch* (MEDIUM)" in text_content

    def test_long_risk_evidence_truncation(self):
        """Evidence strings longer than truncation limits (150 for high, 120 for medium) are truncated."""
        high_ev = "H" * 200
        med_ev = "M" * 200
        report = {
            "risks": [
                {"risk_id": "overflow_high", "severity": "high", "evidence": high_ev},
                {"risk_id": "overflow_med", "severity": "medium", "evidence": med_ev},
            ]
        }
        blocks = format_slack_report_blocks(report)
        high_block = next(b for b in blocks if "High-Priority" in b.get("text", {}).get("text", ""))
        med_block = next(b for b in blocks if "Other Active" in b.get("text", {}).get("text", ""))
        assert "H" * 150 + "..." in high_block["text"]["text"]
        assert "M" * 120 + "..." in med_block["text"]["text"]

    def test_risks_as_strings(self):
        """Risks supplied as raw strings are normalized into medium severity risk blocks."""
        report = {
            "risks": ["unreviewed_pr_bottleneck", "missing_milestone"]
        }
        blocks = format_slack_report_blocks(report)
        other_block = next(b for b in blocks if "Other Active" in b.get("text", {}).get("text", ""))
        assert "Unreviewed Pr Bottleneck" in other_block["text"]["text"]
        assert "Missing Milestone" in other_block["text"]["text"]

    def test_risks_from_nested_metrics_snapshot_and_report(self):
        """Risks are successfully extracted from metricsSnapshot or nested report objects."""
        # 1. From metricsSnapshot.risks
        rep1 = {"metricsSnapshot": {"risks": [{"risk_id": "snap_risk", "severity": "high"}]}}
        b1 = format_slack_report_blocks(rep1)
        assert any("Snap Risk" in b.get("text", {}).get("text", "") for b in b1)

        # 2. From metricsSnapshot.project_health.risk_factors
        rep2 = {"metricsSnapshot": {"project_health": {"risk_factors": [{"risk_id": "snap_factor", "severity": "medium"}]}}}
        b2 = format_slack_report_blocks(rep2)
        assert any("Snap Factor" in b.get("text", {}).get("text", "") for b in b2)

        # 3. From report.project_health.risk_factors
        rep3 = {"report": {"project_health": {"risk_factors": [{"risk_id": "nested_factor", "severity": "high"}]}}}
        b3 = format_slack_report_blocks(rep3)
        assert any("Nested Factor" in b.get("text", {}).get("text", "") for b in b3)

    def test_recommendations_as_dicts_and_strings(self):
        """Recommendations provided as dictionaries or strings are extracted and formatted."""
        report = {
            "recommendations": [
                {"recommendation": "Enable automated dependency scanning."},
                "Conduct architecture review.",
            ]
        }
        blocks = format_slack_report_blocks(report)
        rec_block = next(b for b in blocks if "Recommended Actions" in b.get("text", {}).get("text", ""))
        assert "Enable automated dependency scanning." in rec_block["text"]["text"]
        assert "Conduct architecture review." in rec_block["text"]["text"]

    def test_report_without_summary(self):
        """Report without summary gracefully omits executive summary section."""
        report = {"project_health": {"score": 80, "status": "healthy"}}
        blocks = format_slack_report_blocks(report)
        assert not any("Executive Summary" in b.get("text", {}).get("text", "") for b in blocks)

    def test_report_url_resolution_variations(self, monkeypatch):
        """Tests URL resolution precedence: explicit URL, payload keys, and APP_URL formatting."""
        # 1. explicit_url with invalid scheme falls through
        rep1 = {"report_url": "https://dashboard.example.com/r/100"}
        url1 = _resolve_report_url(rep1, explicit_url="ftp://invalid")
        assert url1 == "https://dashboard.example.com/r/100"

        # 2. payload contains 'url'
        rep2 = {"url": "https://dashboard.example.com/u/200"}
        url2 = _resolve_report_url(rep2)
        assert url2 == "https://dashboard.example.com/u/200"

        # 3. APP_URL without protocol prefix
        monkeypatch.setenv("APP_URL", "internal-analyzer:8080")
        url3 = _resolve_report_url({"project_id": "proj_abc"})
        assert url3 == "http://internal-analyzer:8080/projects/proj_abc"

    def test_unicode_and_internationalization(self):
        """Unicode characters (Gujarati script, emojis, multilingual text) format seamlessly."""
        gujarati_name = "પ્રોજેક્ટ હેલ્થ એનાલાઈઝર"
        emoji_summary = "🚀 Deployment succeeded with 🛡️ security checks passing."
        report = {
            "project_name": gujarati_name,
            "executive_summary": emoji_summary,
            "project_health": {"score": 92, "status": "healthy"},
        }
        blocks = format_slack_report_blocks(report)
        header_text = blocks[0]["text"]["text"]
        summary_text = blocks[2]["text"]["text"]
        assert gujarati_name in header_text
        assert "🚀" in summary_text
        assert "🛡️" in summary_text

    def test_project_id_fallback_naming(self):
        """Project ID fallback format when project_name is missing."""
        report = {"projectId": "abcdef1234567890"}
        blocks = format_slack_report_blocks(report)
        assert "Project (abcdef12)" in blocks[0]["text"]["text"]

    def test_extraction_helpers_with_non_dict_inputs(self):
        """Direct unit testing of extraction helpers when non-dict is passed."""
        assert _extract_health_score(None) == (None, "Unknown", None, None)
        assert _extract_project_info(None) == ("Software Project", None)
        assert _extract_risks(None) == []
        assert _extract_summary(None) == ""
        assert _extract_recommendations(None) == []

    def test_extract_health_score_precedence(self):
        """Top-level health score and status take precedence over nested project_health."""
        report = {
            "health_score": 95,
            "health_status": "healthy",
            "project_health": {
                "score": 40,
                "status": "at_risk",
                "confidence": "high",
                "coverage_ratio": 0.95,
            },
        }
        score, status, conf, cov = _extract_health_score(report)
        assert score == 95
        assert status == "Healthy"
        assert conf == "high"
        assert cov == 0.95

    def test_filter_invalid_entries_in_risks_and_recommendations(self):
        """Invalid types (int, None, empty string) in risks and recommendations are safely skipped."""
        report = {
            "risks": [None, 123, "", {"risk_id": "valid_risk", "severity": "low"}],
            "recommendations": [None, 456, "", {"invalid_key": "val"}, "Valid Recommendation"],
        }
        risks = _extract_risks(report)
        assert len(risks) == 1
        assert risks[0]["risk_id"] == "valid_risk"

        recs = _extract_recommendations(report)
        assert len(recs) == 1
        assert recs[0] == "Valid Recommendation"

        # Non-dict report to _resolve_report_url
        assert _resolve_report_url(None) == DEFAULT_APP_BASE_URL


# ===========================================================================
# 6. Webhook Validation & Security Audit Tests
# ===========================================================================

class TestWebhookValidationAndSecurity:
    def test_validate_webhook_url_missing_scheme(self):
        """Webhook URL with missing scheme is rejected."""
        with pytest.raises(SlackWebhookUrlError, match="missing scheme"):
            validate_webhook_url("//hooks.slack.com/services/T00/B00/X00")

    def test_validate_webhook_url_malformed_ipv6(self):
        """Malformed URL with invalid IPv6 syntax raises SlackWebhookUrlError."""
        with pytest.raises(SlackWebhookUrlError, match="Malformed"):
            validate_webhook_url("https://[invalid-ipv6]")

    def test_validate_webhook_url_userinfo_rejection(self):
        """Webhook URLs with embedded user credentials are strictly rejected (anti-SSRF/credential leak)."""
        with pytest.raises(SlackWebhookUrlError, match="embedded user credentials"):
            validate_webhook_url("https://admin:secret123@hooks.slack.com/services/T00/B00/X00")

    def test_validate_webhook_url_hostname_spoofing(self):
        """Hostnames attempting spoofing or redirection outside slack.com are rejected."""
        with pytest.raises(SlackWebhookUrlError, match="Invalid Slack webhook host"):
            validate_webhook_url("https://hooks.slack.com.attacker.com/services/T00/B00/X00")

        with pytest.raises(SlackWebhookUrlError, match="Invalid Slack webhook host"):
            validate_webhook_url("https://evil-slack.com/services/T00/B00/X00")

        with pytest.raises(SlackWebhookUrlError, match="Invalid Slack webhook host"):
            validate_webhook_url("https://attacker.com/services/T00/B00/X00")

    def test_validate_webhook_url_query_parameters_rejection(self):
        """Query parameters in webhook URLs are rejected."""
        with pytest.raises(SlackWebhookUrlError, match="query parameters"):
            validate_webhook_url("https://hooks.slack.com/services/T00/B00/X00?token=leak")

    def test_validate_webhook_url_fragment_rejection(self):
        """URL fragments in webhook URLs are rejected."""
        with pytest.raises(SlackWebhookUrlError, match="URL fragments"):
            validate_webhook_url("https://hooks.slack.com/services/T00/B00/X00#fragment")

    def test_validate_webhook_url_allowed_hosts(self):
        """Enterprise Slack domains and localhost/127.0.0.1 test endpoints pass validation."""
        assert validate_webhook_url("https://my-org.slack.com/services/T00/B00/X00")
        assert validate_webhook_url("https://localhost/services/T00/B00/X00")
        assert validate_webhook_url("https://127.0.0.1/services/T00/B00/X00")

    def test_mask_webhook_url_edge_cases(self, monkeypatch):
        """Edge cases for mask_webhook_url including paths without scheme, empty paths, and exceptions."""
        # Missing scheme or host
        assert mask_webhook_url("just-a-path-without-scheme") == "<invalid-url>"
        assert mask_webhook_url("https://") == "<invalid-url>"

        # Path without parts
        assert mask_webhook_url("https://hooks.slack.com") == "https://hooks.slack.com/<REDACTED>"
        assert mask_webhook_url("https://hooks.slack.com/") == "https://hooks.slack.com/<REDACTED>"

        # URL with embedded credentials stripped in mask
        masked_userinfo = mask_webhook_url("https://admin:secret@hooks.slack.com/services/T00/B00/X00")
        assert "secret" not in masked_userinfo
        assert "admin" not in masked_userinfo

        # Non-string input
        assert mask_webhook_url(12345) == "<empty>"  # type: ignore

        # Exception handling
        import urllib.parse
        monkeypatch.setattr(urllib.parse, "urlsplit", lambda *a, **kw: (_ for _ in ()).throw(ValueError("forced")))
        assert mask_webhook_url("https://hooks.slack.com/services/T0/B0/X0") == "<malformed-url>"


# ===========================================================================
# 7. Comprehensive HTTP Delivery & Error Handling Tests
# ===========================================================================

class TestHttpDeliveryComprehensive:
    def test_empty_or_non_dict_payload(self):
        """Empty dictionary or non-dict payload is rejected with clear error."""
        # Empty dict with raise_on_error=False
        res1 = post_to_slack_webhook(VALID_WEBHOOK_URL, {}, raise_on_error=False)
        assert res1.success is False
        assert "non-empty" in (res1.error or "")

        # Empty dict with raise_on_error=True
        with pytest.raises(SlackDeliveryError, match="non-empty"):
            post_to_slack_webhook(VALID_WEBHOOK_URL, {}, raise_on_error=True)

        # Non-dict payload
        res2 = post_to_slack_webhook(VALID_WEBHOOK_URL, None, raise_on_error=False)  # type: ignore
        assert res2.success is False

    def test_invalid_webhook_url_in_post(self):
        """Invalid webhook URL in post_to_slack_webhook triggers validation error."""
        res = post_to_slack_webhook("https://attacker.com/webhook", {"text": "hi"}, raise_on_error=False)
        assert res.success is False
        assert "Invalid Slack webhook host" in (res.error or "")

        with pytest.raises(SlackWebhookUrlError):
            post_to_slack_webhook("https://attacker.com/webhook", {"text": "hi"}, raise_on_error=True)

    def test_retry_after_header_variations(self, monkeypatch):
        """Handles missing, non-numeric, negative, and float Retry-After headers."""
        # 1. Missing Retry-After header
        mock_no_header = MagicMock(status_code=429, text="rate_limited", headers={})
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_no_header)
        res_no_header = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert res_no_header.retry_after is None
        assert "unspecified" in (res_no_header.error or "")

        # 2. Non-numeric Retry-After header
        mock_invalid_hdr = MagicMock(status_code=429, text="rate_limited", headers={"Retry-After": "invalid_seconds"})
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_invalid_hdr)
        res_invalid = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert res_invalid.retry_after is None

        # 3. Negative Retry-After header
        mock_neg_hdr = MagicMock(status_code=429, text="rate_limited", headers={"Retry-After": "-15"})
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_neg_hdr)
        res_neg = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert res_neg.retry_after == 0

        # 4. Float Retry-After header
        mock_float_hdr = MagicMock(status_code=429, text="rate_limited", headers={"Retry-After": "14.8"})
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_float_hdr)
        res_float = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert res_float.retry_after == 14

    def test_various_http_error_codes(self, monkeypatch):
        """Verifies behavior across standard HTTP failure status codes."""
        status_codes = [401, 404, 408, 409, 502, 503, 504]
        for sc in status_codes:
            mock_resp = MagicMock(status_code=sc, text=f"error_{sc}")
            monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)
            res = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
            assert res.success is False
            assert res.status_code == sc
            assert f"error_{sc}" in (res.error or "")

    def test_requests_generic_exception(self, monkeypatch):
        """Generic requests.exceptions.RequestException (e.g. TooManyRedirects or generic) is handled gracefully."""
        def _generic_req_error(*args, **kwargs):
            raise requests.exceptions.RequestException("Generic network socket failure")

        monkeypatch.setattr(requests, "post", _generic_req_error)

        res = post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=False)
        assert res.success is False
        assert "Network exception" in (res.error or "")

        with pytest.raises(SlackDeliveryError, match="Network exception"):
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)

    def test_unexpected_exception_raise_on_error(self, monkeypatch):
        """Unexpected runtime exception with raise_on_error=True raises SlackDeliveryError."""
        def _unexpected(*args, **kwargs):
            raise KeyError("critical_internal_key")

        monkeypatch.setattr(requests, "post", _unexpected)

        with pytest.raises(SlackDeliveryError, match="Unexpected error"):
            post_to_slack_webhook(VALID_WEBHOOK_URL, {"text": "test"}, raise_on_error=True)

    def test_custom_requests_session_injection(self):
        """Custom requests.Session is respected for dependency injection and connection pooling."""
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(status_code=200, text="ok")
        mock_session.post.return_value = mock_response

        # In post_to_slack_webhook
        res = post_to_slack_webhook(
            VALID_WEBHOOK_URL,
            {"text": "session_test"},
            session=mock_session,
        )
        assert res.success is True
        mock_session.post.assert_called_once()

        # In send_slack_report
        mock_session.reset_mock()
        report = make_sample_report()
        res_report = send_slack_report(
            report_data=report,
            webhook_url=VALID_WEBHOOK_URL,
            session=mock_session,
        )
        assert res_report.success is True
        mock_session.post.assert_called_once()

    def test_send_slack_report_with_explicit_url(self, monkeypatch):
        """send_slack_report correctly wires explicit report_url and project_name."""
        mock_response = MagicMock(status_code=200, text="ok")
        captured_json = {}

        def _capture(url, json, headers, timeout):
            captured_json.update(json)
            return mock_response

        monkeypatch.setattr(requests, "post", _capture)

        report = make_sample_report()
        res = send_slack_report(
            report_data=report,
            webhook_url=VALID_WEBHOOK_URL,
            project_name="Explicit Project",
            report_url="https://frontend.example.com/reports/exp_1",
        )
        assert res.success is True
        assert "Explicit Project" in captured_json["text"]
        button = captured_json["blocks"][1]["accessory"]
        assert button["url"] == "https://frontend.example.com/reports/exp_1"
