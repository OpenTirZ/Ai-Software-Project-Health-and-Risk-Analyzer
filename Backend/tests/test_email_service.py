"""
Test Suite for Aegis AI Email Service Subsystem.

Comprehensive test coverage covering:
  - SMTP configuration parsing, TLS auto-selection, env variable validation, and password masking
  - Input validation, RFC email format verification, and CRLF / header injection guards
  - Jinja2 template rendering, XSS autoescape verification, full and minimal dataset handling
  - Plain-text fallback generation and direct dashboard link presence
  - MIME multipart/alternative/attachment RFC 5322 structure
  - Asynchronous transport via aiosmtplib with retry, backoff, and exception chaining
  - Synchronous transport via smtplib with SMTPS (port 465) and STARTTLS (port 587) paths
  - Credential security and zero leakage in logging (caplog) and exception strings
  - Public API end-to-end orchestration
"""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
import html
import logging
from pathlib import Path
import re
import smtplib
import socket
import ssl
import time
from typing import Any, Dict, List, Mapping, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import aiosmtplib

from Backend.externalservies.email_service import (
    DEFAULT_MAX_PDF_BYTES,
    DEFAULT_PDF_FILENAME,
    DEFAULT_SMTP_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    AsyncSMTPTransport,
    EmailConfigError,
    EmailSendError,
    EmailSendResult,
    EmailService,
    EmailServiceError,
    EmailTemplateError,
    EmailTemplateRenderer,
    EmailValidationError,
    SMTPConfig,
    SyncSMTPTransport,
    build_plain_text_body,
    build_report_email_message,
    normalize_and_validate_recipients,
    send_report_email,
    send_report_email_sync,
    validate_and_read_pdf,
    validate_dashboard_url,
    validate_email_address,
    validate_header_field,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def valid_env() -> Dict[str, str]:
    """Standard valid environment variables dictionary for testing."""
    return {
        "SMTP_HOST": "smtp.mailgun.org",
        "SMTP_PORT": "587",
        "SMTP_USER": "postmaster@aegis-ai.internal",
        "SMTP_PASS": "SuperSecretPassword123!",
        "SMTP_FROM": "telemetry-alerts@aegis-ai.internal",
        "SMTP_TIMEOUT": "25.0",
        "SMTP_MAX_RETRIES": "3",
    }


@pytest.fixture
def sample_health_summary() -> Dict[str, Any]:
    """Comprehensive health summary payload representing full telemetry analysis."""
    return {
        "health_score": 87.5,
        "status": "GOOD",
        "risk_level": "LOW",
        "score_delta": 4.2,
        "branch": "main",
        "active_flags_count": 2,
        "executive_summary": (
            "Sprint telemetry indicates strong pull request turnaround times and minimal "
            "code review latency. Two minor dependency warnings are scheduled for resolution."
        ),
        "metrics": {
            "pr_velocity": "4.2 PRs/day",
            "review_latency": "2.4 hours",
            "stale_issues": "3 issues",
            "build_pass_rate": "98.5%",
            "test_coverage": "84.2%",
        },
        "active_risks": [
            {
                "title": "Stale Issue Threshold",
                "severity": "medium",
                "message": "Three issues have had no activity for over 30 days.",
                "impact": "Low impact on release schedule; backlog refinement recommended.",
            },
            {
                "title": "Minor Dependency Vulnerability",
                "severity": "low",
                "message": "Transitive dependency package requires bump in next sprint.",
                "impact": "Non-exploitable in production configuration.",
            },
        ],
        "recommendations": [
            {
                "action": "Close or triage 3 stale issues before end of sprint.",
                "detail": "Issue #42, #55, and #89 require maintainer feedback.",
            },
            {
                "action": "Upgrade secondary logging library to patch minor CVE.",
                "detail": "PR #104 has been drafted and is awaiting CI verification.",
            },
        ],
    }


@pytest.fixture
def minimal_health_summary() -> Dict[str, Any]:
    """Minimal health summary payload containing only basic values."""
    return {
        "health_score": 52.0,
        "status": "CAUTION",
    }


@pytest.fixture
def empty_health_summary() -> Dict[str, Any]:
    """Completely empty dictionary representing uninitialized or sparse telemetry."""
    return {}


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Mock valid PDF content starting with standard %PDF- header."""
    return b"%PDF-1.4\n1 0 obj\n<< /Title (Project Health Report) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


@pytest.fixture
def sample_pdf_file(tmp_path: Path, sample_pdf_bytes: bytes) -> Path:
    """Temporary real file containing valid PDF bytes."""
    pdf_path = tmp_path / "valid_report.pdf"
    pdf_path.write_bytes(sample_pdf_bytes)
    return pdf_path


@pytest.fixture
def valid_config(valid_env: Dict[str, str]) -> SMTPConfig:
    """Instantiated SMTPConfig from valid environment variables."""
    return SMTPConfig.from_env(valid_env)


# ---------------------------------------------------------------------------
# Test Suite 1: SMTPConfig Configuration & Environment Parsing
# ---------------------------------------------------------------------------
class TestSMTPConfig:
    """Tests covering configuration dataclass parsing, defaults, and error cases."""

    def test_config_from_valid_env(self, valid_env: Dict[str, str]) -> None:
        """Verify normal parsing of all required and optional environment variables."""
        cfg = SMTPConfig.from_env(valid_env)
        assert cfg.host == "smtp.mailgun.org"
        assert cfg.port == 587
        assert cfg.user == "postmaster@aegis-ai.internal"
        assert cfg.password == "SuperSecretPassword123!"
        assert cfg.from_address == "telemetry-alerts@aegis-ai.internal"
        assert cfg.use_tls is False
        assert cfg.start_tls is True
        assert cfg.timeout == 25.0
        assert cfg.max_retries == 3

    @pytest.mark.parametrize(
        "missing_key",
        ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"],
    )
    def test_config_missing_single_required_var(
        self, valid_env: Dict[str, str], missing_key: str
    ) -> None:
        """Verify that omitting any individual required variable raises EmailConfigError."""
        env_copy = dict(valid_env)
        del env_copy[missing_key]
        with pytest.raises(EmailConfigError) as exc_info:
            SMTPConfig.from_env(env_copy)
        assert missing_key in exc_info.value.missing_vars
        assert missing_key in str(exc_info.value)
        # Verify secret credentials do not appear in the error message
        assert "SuperSecretPassword123!" not in str(exc_info.value)

    @pytest.mark.parametrize(
        "missing_keys",
        [
            ("SMTP_HOST", "SMTP_PORT"),
            ("SMTP_USER", "SMTP_PASS"),
            ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"),
            ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"),
        ],
    )
    def test_config_missing_multiple_required_vars(
        self, valid_env: Dict[str, str], missing_keys: tuple[str, ...]
    ) -> None:
        """Verify that multiple missing variables are all listed in EmailConfigError."""
        env_copy = dict(valid_env)
        for key in missing_keys:
            del env_copy[key]
        with pytest.raises(EmailConfigError) as exc_info:
            SMTPConfig.from_env(env_copy)
        for key in missing_keys:
            assert key in exc_info.value.missing_vars
            assert key in str(exc_info.value)

    def test_config_empty_env(self) -> None:
        """Verify behavior when passed an empty dictionary."""
        with pytest.raises(EmailConfigError) as exc_info:
            SMTPConfig.from_env({})
        assert set(exc_info.value.missing_vars) == {
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
        }

    @pytest.mark.parametrize(
        "invalid_port",
        ["abc", "587.5", "five-eight-seven", "port587", " "],
    )
    def test_config_invalid_non_numeric_port(
        self, valid_env: Dict[str, str], invalid_port: str
    ) -> None:
        """Verify that non-numeric port strings raise EmailConfigError."""
        env_copy = dict(valid_env)
        env_copy["SMTP_PORT"] = invalid_port
        with pytest.raises(EmailConfigError) as exc_info:
            SMTPConfig.from_env(env_copy)
        assert "not a valid integer" in str(exc_info.value)
        assert exc_info.value.invalid_var == "SMTP_PORT"

    @pytest.mark.parametrize("out_of_range_port", [-10, 0, 65536, 100000])
    def test_config_out_of_range_port(
        self, valid_env: Dict[str, str], out_of_range_port: int
    ) -> None:
        """Verify that ports outside 1-65535 raise EmailConfigError."""
        env_copy = dict(valid_env)
        env_copy["SMTP_PORT"] = str(out_of_range_port)
        with pytest.raises(EmailConfigError) as exc_info:
            SMTPConfig.from_env(env_copy)
        assert "out of allowable range" in str(exc_info.value)
        assert exc_info.value.invalid_var == "SMTP_PORT"

    @pytest.mark.parametrize(
        "port,expected_use_tls,expected_start_tls",
        [
            (465, True, False),
            (587, False, True),
            (25, False, True),
            (2525, False, True),
        ],
    )
    def test_config_tls_auto_selection_by_port(
        self,
        valid_env: Dict[str, str],
        port: int,
        expected_use_tls: bool,
        expected_start_tls: bool,
    ) -> None:
        """Verify port 465 auto-selects implicit TLS, while other ports default to STARTTLS."""
        env_copy = dict(valid_env)
        env_copy["SMTP_PORT"] = str(port)
        cfg = SMTPConfig.from_env(env_copy)
        assert cfg.port == port
        assert cfg.use_tls is expected_use_tls
        assert cfg.start_tls is expected_start_tls

    @pytest.mark.parametrize(
        "override_use_tls,override_start_tls,expected_use_tls,expected_start_tls",
        [
            ("true", "false", True, False),
            ("false", "true", False, True),
            ("1", "0", True, False),
            ("0", "1", False, True),
        ],
    )
    def test_config_tls_explicit_env_overrides(
        self,
        valid_env: Dict[str, str],
        override_use_tls: str,
        override_start_tls: str,
        expected_use_tls: bool,
        expected_start_tls: bool,
    ) -> None:
        """Verify explicit SMTP_USE_TLS and SMTP_START_TLS environment variables take precedence."""
        env_copy = dict(valid_env)
        env_copy["SMTP_PORT"] = "587"
        env_copy["SMTP_USE_TLS"] = override_use_tls
        env_copy["SMTP_START_TLS"] = override_start_tls
        cfg = SMTPConfig.from_env(env_copy)
        assert cfg.use_tls is expected_use_tls
        assert cfg.start_tls is expected_start_tls

    def test_config_from_address_defaults_to_user(self, valid_env: Dict[str, str]) -> None:
        """Verify that when SMTP_FROM is not supplied, from_address falls back to SMTP_USER."""
        env_copy = dict(valid_env)
        del env_copy["SMTP_FROM"]
        cfg = SMTPConfig.from_env(env_copy)
        assert cfg.from_address == env_copy["SMTP_USER"]

    def test_config_from_address_parameter_override(self, valid_env: Dict[str, str]) -> None:
        """Verify that explicit override_from argument overrides both SMTP_FROM and SMTP_USER."""
        cfg = SMTPConfig.from_env(valid_env, override_from="custom-sender@override.com")
        assert cfg.from_address == "custom-sender@override.com"

    def test_config_password_alias_support(self, valid_env: Dict[str, str]) -> None:
        """Verify SMTP_PASSWORD is recognized if SMTP_PASS is omitted."""
        env_copy = dict(valid_env)
        del env_copy["SMTP_PASS"]
        env_copy["SMTP_PASSWORD"] = "AliasPass999!"
        cfg = SMTPConfig.from_env(env_copy)
        assert cfg.password == "AliasPass999!"

    def test_config_repr_and_str_mask_password(self, valid_config: SMTPConfig) -> None:
        """Verify that password is strictly masked in repr and str to avoid logging leakage."""
        repr_str = repr(valid_config)
        str_str = str(valid_config)
        assert "SuperSecretPassword123!" not in repr_str
        assert "SuperSecretPassword123!" not in str_str
        assert "password='***'" in repr_str
        assert "password='***'" in str_str

    def test_config_reading_from_real_os_environ(
        self, monkeypatch: pytest.MonkeyPatch, valid_env: Dict[str, str]
    ) -> None:
        """Verify SMTPConfig.from_env() resolves from os.environ when no env dict is passed."""
        for k, v in valid_env.items():
            monkeypatch.setenv(k, v)
        cfg = SMTPConfig.from_env()
        assert cfg.host == valid_env["SMTP_HOST"]
        assert cfg.port == int(valid_env["SMTP_PORT"])
        assert cfg.user == valid_env["SMTP_USER"]


# ---------------------------------------------------------------------------
# Test Suite 2: Input Validation, RFC Compliance & Header Injection Guards
# ---------------------------------------------------------------------------
class TestInputValidation:
    """Tests covering security sanitization, header injection, and data formatting."""

    @pytest.mark.parametrize(
        "header_value",
        [
            "Normal Header Value",
            "Project-Name_123",
            "Release 2.4.0 (Sprint 12)",
            "user@domain.com",
        ],
    )
    def test_validate_header_field_valid(self, header_value: str) -> None:
        """Verify clean header fields pass validation unchanged."""
        assert validate_header_field(header_value, "test_field") == header_value

    @pytest.mark.parametrize(
        "injection_payload",
        [
            "Subject: Injected\r\nBcc: evil@hacker.com",
            "test\nvalue",
            "test\rvalue",
            "Header\r\n",
            "\nLeadingNewline",
            "TrailingNewline\r",
            "Multiple\r\nLines\r\nInjected",
        ],
    )
    def test_validate_header_field_rejects_newlines(self, injection_payload: str) -> None:
        """Verify that any presence of CR or LF in header fields triggers EmailValidationError."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_header_field(injection_payload, "subject")
        assert "Header injection detected" in str(exc_info.value)
        assert exc_info.value.field_name == "subject"

    def test_validate_header_field_rejects_non_string(self) -> None:
        """Verify non-string values raise EmailValidationError."""
        with pytest.raises(EmailValidationError):
            validate_header_field(12345, "field")  # type: ignore

    @pytest.mark.parametrize(
        "valid_email",
        [
            "simple@example.com",
            "first.last@company.org",
            "user+tag@domain.co.uk",
            "dev_team@sub.domain.io",
            "a.b-c_d+e@domain.net",
        ],
    )
    def test_validate_email_address_valid(self, valid_email: str) -> None:
        """Verify valid RFC-compliant email addresses pass."""
        assert validate_email_address(valid_email) == valid_email

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "",
            "   ",
            "plainaddress",
            "@missing-user.com",
            "missing-domain@",
            "user@domain",
            "user@.com",
            "user name@domain.com",
            "user@domain..com",
        ],
    )
    def test_validate_email_address_invalid(self, invalid_email: str) -> None:
        """Verify malformed email addresses raise EmailValidationError."""
        with pytest.raises(EmailValidationError):
            validate_email_address(invalid_email)

    def test_validate_email_address_header_injection(self) -> None:
        """Verify email addresses with injected CRLF are rejected."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_email_address("victim@example.com\r\nBcc: spy@evil.com")
        assert "Header injection detected" in str(exc_info.value)

    def test_normalize_recipients_single_string(self) -> None:
        """Verify single email string is normalized to a single-element list."""
        assert normalize_and_validate_recipients("admin@example.com") == ["admin@example.com"]

    def test_normalize_recipients_comma_separated(self) -> None:
        """Verify comma-separated email string is parsed into individual addresses."""
        res = normalize_and_validate_recipients("alice@example.com, bob@example.com, charlie@example.com")
        assert res == ["alice@example.com", "bob@example.com", "charlie@example.com"]

    def test_normalize_recipients_list_and_set(self) -> None:
        """Verify sequences and sets are correctly normalized."""
        recipients = ["dev1@team.internal", "dev2@team.internal"]
        assert normalize_and_validate_recipients(recipients) == recipients

    def test_normalize_recipients_deduplication(self) -> None:
        """Verify duplicate recipient entries are pruned while preserving order."""
        recipients = ["dup@example.com", "other@example.com", "dup@example.com"]
        assert normalize_and_validate_recipients(recipients) == ["dup@example.com", "other@example.com"]

    @pytest.mark.parametrize("empty_input", [None, [], "", "   "])
    def test_normalize_recipients_empty_disallowed(self, empty_input: Any) -> None:
        """Verify empty recipient collections raise EmailValidationError when allow_empty=False."""
        with pytest.raises(EmailValidationError) as exc_info:
            normalize_and_validate_recipients(empty_input, field_name="to", allow_empty=False)
        assert exc_info.value.field_name == "to"

    @pytest.mark.parametrize("empty_input", [None, [], "", "   "])
    def test_normalize_recipients_empty_allowed_for_cc_bcc(self, empty_input: Any) -> None:
        """Verify CC and BCC fields permit empty collections when allow_empty=True."""
        assert normalize_and_validate_recipients(empty_input, field_name="cc", allow_empty=True) == []

    @pytest.mark.parametrize(
        "valid_url",
        [
            "http://localhost:3000/dashboard",
            "https://aegis-ai.internal/projects/42",
            "https://app.telemetry.io:8443/view?proj=aegis#metrics",
            "http://127.0.0.1:8000/reports/executive",
        ],
    )
    def test_validate_dashboard_url_valid(self, valid_url: str) -> None:
        """Verify valid HTTP and HTTPS URLs are accepted."""
        assert validate_dashboard_url(valid_url) == valid_url

    @pytest.mark.parametrize(
        "bad_url",
        [
            "",
            "   ",
            "javascript:alert('pwned')",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            "ftp://ftp.example.com/reports",
            "file:///etc/passwd",
            "/relative/path/dashboard",
            "relative/path",
            "http://",
            "https://",
            "dashboard.internal",
        ],
    )
    def test_validate_dashboard_url_invalid(self, bad_url: str) -> None:
        """Verify malicious, unsupported schemes or scheme-less URLs raise EmailValidationError."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_dashboard_url(bad_url)
        assert exc_info.value.field_name == "dashboard_url"

    def test_validate_dashboard_url_header_injection(self) -> None:
        """Verify CRLF in dashboard_url is blocked."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_dashboard_url("https://aegis.internal\r\nInjected-Header: 1")
        assert "Header injection detected" in str(exc_info.value)

    def test_validate_and_read_pdf_valid_bytes(self, sample_pdf_bytes: bytes) -> None:
        """Verify byte input validation and length checking."""
        payload, size = validate_and_read_pdf(sample_pdf_bytes)
        assert payload == sample_pdf_bytes
        assert size == len(sample_pdf_bytes)

    def test_validate_and_read_pdf_valid_path(self, sample_pdf_file: Path, sample_pdf_bytes: bytes) -> None:
        """Verify pathlib.Path object input resolution and reading."""
        payload, size = validate_and_read_pdf(sample_pdf_file)
        assert payload == sample_pdf_bytes
        assert size == len(sample_pdf_bytes)

    def test_validate_and_read_pdf_valid_str_path(self, sample_pdf_file: Path, sample_pdf_bytes: bytes) -> None:
        """Verify string path input resolution and reading."""
        payload, size = validate_and_read_pdf(str(sample_pdf_file))
        assert payload == sample_pdf_bytes
        assert size == len(sample_pdf_bytes)

    def test_validate_and_read_pdf_empty_bytes(self) -> None:
        """Verify 0-byte PDF content raises EmailValidationError."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_and_read_pdf(b"")
        assert "empty (0 bytes)" in str(exc_info.value)

    def test_validate_and_read_pdf_empty_file(self, tmp_path: Path) -> None:
        """Verify 0-byte PDF file on disk raises EmailValidationError."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.write_bytes(b"")
        with pytest.raises(EmailValidationError) as exc_info:
            validate_and_read_pdf(empty_file)
        assert "empty (0 bytes)" in str(exc_info.value)

    def test_validate_and_read_pdf_nonexistent_file(self, tmp_path: Path) -> None:
        """Verify non-existent filesystem path raises EmailValidationError."""
        non_existent = tmp_path / "does_not_exist.pdf"
        with pytest.raises(EmailValidationError) as exc_info:
            validate_and_read_pdf(non_existent)
        assert "not found" in str(exc_info.value)

    def test_validate_and_read_pdf_directory_path(self, tmp_path: Path) -> None:
        """Verify directory path raises EmailValidationError."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_and_read_pdf(tmp_path)
        assert "not a regular file" in str(exc_info.value)

    def test_validate_and_read_pdf_oversized_limit(self, sample_pdf_bytes: bytes) -> None:
        """Verify payloads exceeding max size limit raise EmailValidationError."""
        small_limit = len(sample_pdf_bytes) - 1
        with pytest.raises(EmailValidationError) as exc_info:
            validate_and_read_pdf(sample_pdf_bytes, max_size_bytes=small_limit)
        assert "exceeds maximum allowable limit" in str(exc_info.value)

    def test_validate_and_read_pdf_unsupported_type(self) -> None:
        """Verify unsupported argument types raise EmailValidationError."""
        with pytest.raises(EmailValidationError) as exc_info:
            validate_and_read_pdf(12345)  # type: ignore
        assert "must be bytes or a filesystem Path" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test Suite 3: Jinja2 Template Rendering & XSS Autoescape Verification
# ---------------------------------------------------------------------------
class TestTemplateRenderer:
    """Tests covering Jinja2 HTML template compilation, styling, and injection safety."""

    @pytest.fixture
    def renderer(self) -> EmailTemplateRenderer:
        return EmailTemplateRenderer()

    def test_template_renders_full_summary(
        self,
        renderer: EmailTemplateRenderer,
        sample_health_summary: Dict[str, Any],
    ) -> None:
        """Verify complete rendering with all health summary fields and dashboard link."""
        rendered = renderer.render(
            project_name="Aegis-Core",
            health_summary=sample_health_summary,
            dashboard_url="https://aegis-ai.internal/dashboards/aegis-core",
            pdf_filename="aegis_core_sprint12.pdf",
        )
        assert "<!DOCTYPE html" in rendered
        assert "Aegis-Core" in rendered
        assert "87.5" in rendered
        assert "GOOD" in rendered
        assert "https://aegis-ai.internal/dashboards/aegis-core" in rendered
        assert "aegis_core_sprint12.pdf" in rendered
        assert "Stale Issue Threshold" in rendered
        assert "Close or triage 3 stale issues" in rendered
        assert "Pr Velocity" in rendered or "pr velocity" in rendered.lower()

    def test_template_renders_minimal_summary(
        self,
        renderer: EmailTemplateRenderer,
        minimal_health_summary: Dict[str, Any],
    ) -> None:
        """Verify rendering succeeds gracefully when optional fields are absent."""
        rendered = renderer.render(
            project_name="Minimal-Service",
            health_summary=minimal_health_summary,
            dashboard_url="https://dashboard.example.com",
        )
        assert "Minimal-Service" in rendered
        assert "52.0" in rendered
        assert "CAUTION" in rendered
        assert "https://dashboard.example.com" in rendered
        assert "Open Interactive Health Dashboard" in rendered

    def test_template_renders_empty_summary(
        self,
        renderer: EmailTemplateRenderer,
        empty_health_summary: Dict[str, Any],
    ) -> None:
        """Verify rendering handles an empty dictionary without throwing KeyError or crashing."""
        rendered = renderer.render(
            project_name="Empty-Project",
            health_summary=empty_health_summary,
            dashboard_url="http://localhost:8080/empty",
        )
        assert "Empty-Project" in rendered
        assert "http://localhost:8080/empty" in rendered
        assert "UNKNOWN" in rendered or "--" in rendered

    @pytest.mark.parametrize(
        "status_val",
        ["GOOD", "HEALTHY", "CAUTION", "MODERATE", "WARNING", "AT RISK", "CRITICAL", "UNKNOWN"],
    )
    def test_template_status_badge_variants(
        self, renderer: EmailTemplateRenderer, status_val: str
    ) -> None:
        """Verify each project status string variant renders properly."""
        summary = {"status": status_val, "health_score": 75.0}
        rendered = renderer.render(
            project_name="Status-Test",
            health_summary=summary,
            dashboard_url="https://test.local",
        )
        assert status_val in rendered

    @pytest.mark.parametrize("risk_val", ["LOW", "MEDIUM", "MODERATE", "HIGH", "CRITICAL"])
    def test_template_risk_level_variants(
        self, renderer: EmailTemplateRenderer, risk_val: str
    ) -> None:
        """Verify each risk level string variant renders properly."""
        summary = {"risk_level": risk_val, "health_score": 60.0}
        rendered = renderer.render(
            project_name="Risk-Test",
            health_summary=summary,
            dashboard_url="https://test.local",
        )
        assert risk_val in rendered

    def test_template_escapes_xss_in_project_name(self, renderer: EmailTemplateRenderer) -> None:
        """Verify malicious HTML tags in project_name are automatically escaped by Jinja2."""
        malicious_name = "<script>alert('pwned')</script>"
        rendered = renderer.render(
            project_name=malicious_name,
            health_summary={"status": "GOOD"},
            dashboard_url="https://safe.local",
        )
        assert "<script>" not in rendered
        assert "&lt;script&gt;alert(&#39;pwned&#39;)&lt;/script&gt;" in rendered or "&lt;script&gt;" in rendered

    def test_template_escapes_xss_in_summary_and_risks(
        self, renderer: EmailTemplateRenderer
    ) -> None:
        """Verify malicious HTML in summary statement and risk messages is strictly escaped."""
        malicious_summary = {
            "status": "GOOD",
            "executive_summary": '<b onclick="steal()">Click me</b>',
            "active_risks": [
                {
                    "title": '<img src=x onerror="alert(1)">',
                    "severity": "high",
                    "message": '"><script>alert(2)</script>',
                }
            ],
            "recommendations": ['<iframe src="evil.com"></iframe>'],
        }
        rendered = renderer.render(
            project_name="Security-Test",
            health_summary=malicious_summary,
            dashboard_url="https://safe.local",
        )
        assert "<script>" not in rendered
        assert "<iframe" not in rendered
        assert "<img src=x" not in rendered
        assert "&lt;script&gt;" in rendered
        assert "&lt;iframe" in rendered

    def test_template_missing_directory_raises_error(self, tmp_path: Path) -> None:
        """Verify non-existent template directory results in EmailTemplateError upon render."""
        bad_dir = tmp_path / "non_existent_templates_dir"
        renderer = EmailTemplateRenderer(template_dir=bad_dir)
        with pytest.raises(EmailTemplateError) as exc_info:
            renderer.render(
                project_name="Test",
                health_summary={},
                dashboard_url="https://test.local",
            )
        assert "not found" in str(exc_info.value)

    def test_empirical_template_render_and_file_inspection(
        self,
        renderer: EmailTemplateRenderer,
        sample_health_summary: Dict[str, Any],
        minimal_health_summary: Dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """
        Empirically render the template once with full data and once with minimal data,
        saving both to disk and confirming the presence of the direct dashboard links.
        """
        target_url = "https://aegis-ai.internal/dashboards/empirical-verification"

        # 1. Full data render
        full_html = renderer.render(
            project_name="Empirical-Full-Project",
            health_summary=sample_health_summary,
            dashboard_url=target_url,
            pdf_filename="empirical_full.pdf",
        )
        full_out_file = tmp_path / "rendered_full.html"
        full_out_file.write_text(full_html, encoding="utf-8")
        assert full_out_file.exists()
        assert full_out_file.stat().st_size > 1000
        assert target_url in full_out_file.read_text(encoding="utf-8")

        # 2. Minimal data render
        min_html = renderer.render(
            project_name="Empirical-Min-Project",
            health_summary=minimal_health_summary,
            dashboard_url=target_url,
            pdf_filename="empirical_min.pdf",
        )
        min_out_file = tmp_path / "rendered_min.html"
        min_out_file.write_text(min_html, encoding="utf-8")
        assert min_out_file.exists()
        assert min_out_file.stat().st_size > 500
        assert target_url in min_out_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test Suite 4: Plain-Text Fallback Builder
# ---------------------------------------------------------------------------
class TestPlainTextBuilder:
    """Tests covering ASCII plain-text fallback generation."""

    def test_plain_text_full_summary(self, sample_health_summary: Dict[str, Any]) -> None:
        """Verify plain-text output contains all core sections and metadata."""
        text = build_plain_text_body(
            project_name="Aegis-CLI",
            health_summary=sample_health_summary,
            dashboard_url="https://dashboard.aegis.io/projects/cli",
            pdf_filename="cli_report.pdf",
        )
        assert "Aegis-CLI" in text
        assert "Status:       GOOD" in text
        assert "Health Score: 87.5/100" in text
        assert "Risk Level:   LOW" in text
        assert "https://dashboard.aegis.io/projects/cli" in text
        assert "cli_report.pdf" in text
        assert "KEY TELEMETRY METRICS:" in text
        assert "ACTIVE RISKS & BOTTLENECKS" in text
        assert "RECOMMENDED ACTIONS:" in text

    def test_plain_text_minimal_summary(self, minimal_health_summary: Dict[str, Any]) -> None:
        """Verify plain-text output formats gracefully with minimal data."""
        text = build_plain_text_body(
            project_name="Minimal-App",
            health_summary=minimal_health_summary,
            dashboard_url="https://app.example.com",
        )
        assert "Minimal-App" in text
        assert "Status:       CAUTION" in text
        assert "Health Score: 52.0/100" in text
        assert "https://app.example.com" in text

    def test_plain_text_empty_summary(self, empty_health_summary: Dict[str, Any]) -> None:
        """Verify plain-text output handles empty dictionaries without error."""
        text = build_plain_text_body(
            project_name="Empty-App",
            health_summary=empty_health_summary,
            dashboard_url="https://empty.example.com",
        )
        assert "Empty-App" in text
        assert "Status:       UNKNOWN" in text
        assert "Health Score: N/A" in text
        assert "https://empty.example.com" in text


# ---------------------------------------------------------------------------
# Test Suite 5: MIME Message RFC 5322 Construction & Attachment Integrity
# ---------------------------------------------------------------------------
class TestMIMEMessageBuilder:
    """Tests covering multi-part email construction, MIME types, and header values."""

    def test_message_structure_and_headers(
        self,
        valid_config: SMTPConfig,
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
    ) -> None:
        """Verify RFC 5322 multi-part structure: alternative (text/plain + text/html) + PDF attachment."""
        msg = build_report_email_message(
            config=valid_config,
            to=["lead-engineer@aegis-ai.internal", "manager@aegis-ai.internal"],
            project_name="Core-API",
            health_summary=sample_health_summary,
            dashboard_url="https://aegis-ai.internal/core-api",
            pdf_data=sample_pdf_bytes,
            pdf_filename="core_api_assessment.pdf",
            cc=["qa-lead@aegis-ai.internal"],
            bcc=["compliance-archive@aegis-ai.internal"],
            reply_to="support@aegis-ai.internal",
        )

        assert isinstance(msg, EmailMessage)
        assert msg["From"] == valid_config.from_address
        assert msg["To"] == "lead-engineer@aegis-ai.internal, manager@aegis-ai.internal"
        assert msg["Cc"] == "qa-lead@aegis-ai.internal"
        assert msg["Bcc"] == "compliance-archive@aegis-ai.internal"
        assert msg["Reply-To"] == "support@aegis-ai.internal"
        assert "[Aegis AI] Health Report: Core-API - GOOD (87.5/100)" in msg["Subject"]

        # Check payload parts: should be multipart/mixed
        assert msg.is_multipart()
        parts = list(msg.iter_parts())
        assert len(parts) >= 2  # alternative container + attachment

        # Find alternative part
        alt_part = None
        attachment_part = None
        for part in parts:
            if part.get_content_type() == "multipart/alternative":
                alt_part = part
            elif part.get_content_type() == "application/pdf":
                attachment_part = part

        assert alt_part is not None, "multipart/alternative container missing"
        assert attachment_part is not None, "application/pdf attachment part missing"

        # Inspect subparts of alternative
        alt_subparts = list(alt_part.iter_parts())
        content_types = [p.get_content_type() for p in alt_subparts]
        assert "text/plain" in content_types
        assert "text/html" in content_types

        # Verify plain-text content
        plain_part = next(p for p in alt_subparts if p.get_content_type() == "text/plain")
        plain_content = plain_part.get_content()
        assert "https://aegis-ai.internal/core-api" in plain_content

        # Verify HTML content
        html_part = next(p for p in alt_subparts if p.get_content_type() == "text/html")
        html_content = html_part.get_content()
        assert "https://aegis-ai.internal/core-api" in html_content
        assert "Core-API" in html_content

        # Verify attachment properties
        assert attachment_part.get_filename() == "core_api_assessment.pdf"
        assert attachment_part.get_content_type() == "application/pdf"
        assert attachment_part.get_content() == sample_pdf_bytes

    def test_message_subject_custom_override(
        self,
        valid_config: SMTPConfig,
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
    ) -> None:
        """Verify subject_override takes precedence when provided."""
        custom_subj = "URGENT: Executive Alert - Project Health Degraded"
        msg = build_report_email_message(
            config=valid_config,
            to=["alerts@company.internal"],
            project_name="Core-API",
            health_summary=sample_health_summary,
            dashboard_url="https://dashboard.company.internal",
            pdf_data=sample_pdf_bytes,
            subject_override=custom_subj,
        )
        assert msg["Subject"] == custom_subj

    def test_message_rejects_header_injection_in_subject_override(
        self,
        valid_config: SMTPConfig,
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
    ) -> None:
        """Verify CRLF in subject_override triggers EmailValidationError."""
        with pytest.raises(EmailValidationError) as exc_info:
            build_report_email_message(
                config=valid_config,
                to=["alerts@company.internal"],
                project_name="Core-API",
                health_summary=sample_health_summary,
                dashboard_url="https://dashboard.company.internal",
                pdf_data=sample_pdf_bytes,
                subject_override="Injected\r\nSubject",
            )
        assert "Header injection detected" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test Suite 6: Asynchronous Transport (aiosmtplib) with Retry & Backoff
# ---------------------------------------------------------------------------
class TestAsyncSMTPTransport:
    """Tests covering aiosmtplib execution, mock network calls, retry, and error wrapping."""

    @pytest.mark.asyncio
    async def test_async_send_success_first_attempt(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify successful async send dispatches via aiosmtplib on first attempt."""
        msg = build_report_email_message(
            config=valid_config,
            to=["recipient@test.com"],
            project_name="Core",
            health_summary=sample_health_summary,
            dashboard_url="https://test.com",
            pdf_data=sample_pdf_bytes,
        )

        mock_smtp = AsyncMock()
        mock_smtp.__aenter__.return_value = mock_smtp

        with patch("aiosmtplib.SMTP", return_value=mock_smtp) as mock_cls:
            transport = AsyncSMTPTransport()
            result = await transport.send(msg, valid_config)

            mock_cls.assert_called_once_with(
                hostname=valid_config.host,
                port=valid_config.port,
                use_tls=valid_config.use_tls,
                start_tls=valid_config.start_tls,
                timeout=valid_config.timeout,
            )
            mock_smtp.login.assert_awaited_once_with(valid_config.user, valid_config.password)
            mock_smtp.send_message.assert_awaited_once_with(msg)

            assert result.success is True
            assert result.attempts == 1
            assert result.transport == "aiosmtplib"
            assert result.recipients == ["recipient@test.com"]

    @pytest.mark.asyncio
    async def test_async_send_retry_transient_error_then_success(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify transport retries on transient connection errors and succeeds when connection recovers."""
        msg = build_report_email_message(
            config=valid_config,
            to=["recipient@test.com"],
            project_name="Core",
            health_summary=sample_health_summary,
            dashboard_url="https://test.com",
            pdf_data=sample_pdf_bytes,
        )

        # Attempt 1: ConnectionRefusedError, Attempt 2: Success
        mock_smtp_fail = AsyncMock()
        mock_smtp_fail.__aenter__.side_effect = ConnectionRefusedError("Connection refused by SMTP relay")

        mock_smtp_ok = AsyncMock()
        mock_smtp_ok.__aenter__.return_value = mock_smtp_ok

        with patch("aiosmtplib.SMTP", side_effect=[mock_smtp_fail, mock_smtp_ok]), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            transport = AsyncSMTPTransport()
            result = await transport.send(msg, valid_config)

            assert result.success is True
            assert result.attempts == 2
            mock_sleep.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_send_exhausts_retries_raises_email_send_error(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify that when all retries are exhausted, EmailSendError is raised with cause chained."""
        msg = build_report_email_message(
            config=valid_config,
            to=["recipient@test.com"],
            project_name="Core",
            health_summary=sample_health_summary,
            dashboard_url="https://test.com",
            pdf_data=sample_pdf_bytes,
        )

        orig_error = aiosmtplib.SMTPConnectError("Connection timed out")
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__.side_effect = orig_error

        with patch("aiosmtplib.SMTP", return_value=mock_smtp), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            transport = AsyncSMTPTransport()
            with pytest.raises(EmailSendError) as exc_info:
                await transport.send(msg, valid_config)

            assert "Failed to transmit email after" in str(exc_info.value)
            assert exc_info.value.attempts == valid_config.max_retries
            assert exc_info.value.host == valid_config.host
            assert exc_info.value.port == valid_config.port
            # Verify exception chaining (__cause__)
            assert exc_info.value.__cause__ is orig_error

    @pytest.mark.asyncio
    async def test_async_send_fatal_unexpected_error_fails_immediately(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify non-transient unexpected errors fail without retrying."""
        msg = build_report_email_message(
            config=valid_config,
            to=["recipient@test.com"],
            project_name="Core",
            health_summary=sample_health_summary,
            dashboard_url="https://test.com",
            pdf_data=sample_pdf_bytes,
        )

        fatal_exc = ValueError("Unexpected configuration state")
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__.side_effect = fatal_exc

        with patch("aiosmtplib.SMTP", return_value=mock_smtp), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            transport = AsyncSMTPTransport()
            with pytest.raises(EmailSendError) as exc_info:
                await transport.send(msg, valid_config)

            assert exc_info.value.attempts == 1
            assert exc_info.value.__cause__ is fatal_exc
            mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test Suite 7: Synchronous Transport (smtplib) with SMTPS & STARTTLS
# ---------------------------------------------------------------------------
class TestSyncSMTPTransport:
    """Tests covering standard library smtplib execution and both TLS pathways."""

    def test_sync_send_port_587_starttls_success(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify synchronous transmission on port 587 invokes starttls() and login()."""
        msg = build_report_email_message(
            config=valid_config,
            to=["sync-lead@example.com"],
            project_name="SyncProject",
            health_summary=sample_health_summary,
            dashboard_url="https://test.local",
            pdf_data=sample_pdf_bytes,
        )

        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server) as mock_cls:
            transport = SyncSMTPTransport()
            result = transport.send(msg, valid_config)

            mock_cls.assert_called_once_with(
                host=valid_config.host,
                port=valid_config.port,
                timeout=valid_config.timeout,
            )
            mock_server.ehlo.assert_called()
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with(valid_config.user, valid_config.password)
            mock_server.send_message.assert_called_once_with(msg)
            mock_server.quit.assert_called_once()

            assert result.success is True
            assert result.transport == "smtplib"
            assert result.attempts == 1

    def test_sync_send_port_465_implicit_ssl_success(
        self, valid_env: Dict[str, str], sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify synchronous transmission on port 465 uses smtplib.SMTP_SSL and does NOT call starttls()."""
        env_465 = dict(valid_env)
        env_465["SMTP_PORT"] = "465"
        cfg_465 = SMTPConfig.from_env(env_465)

        msg = build_report_email_message(
            config=cfg_465,
            to=["ssl-user@example.com"],
            project_name="SSLProject",
            health_summary=sample_health_summary,
            dashboard_url="https://ssl.test.local",
            pdf_data=sample_pdf_bytes,
        )

        mock_ssl_server = MagicMock()
        with patch("smtplib.SMTP_SSL", return_value=mock_ssl_server) as mock_cls, \
             patch("smtplib.SMTP") as mock_plain_smtp:
            transport = SyncSMTPTransport()
            result = transport.send(msg, cfg_465)

            mock_cls.assert_called_once_with(
                host=cfg_465.host,
                port=465,
                timeout=cfg_465.timeout,
            )
            mock_plain_smtp.assert_not_called()
            mock_ssl_server.starttls.assert_not_called()
            mock_ssl_server.login.assert_called_once_with(cfg_465.user, cfg_465.password)
            mock_ssl_server.send_message.assert_called_once_with(msg)

            assert result.success is True
            assert result.transport == "smtplib"

    def test_sync_send_retry_and_exhaustion(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify sync transport executes retries on transient errors and wraps fatal failures in EmailSendError."""
        msg = build_report_email_message(
            config=valid_config,
            to=["retry@example.com"],
            project_name="RetryProject",
            health_summary=sample_health_summary,
            dashboard_url="https://test.local",
            pdf_data=sample_pdf_bytes,
        )

        orig_error = smtplib.SMTPServerDisconnected("Connection unexpectedly lost")
        mock_server = MagicMock()
        mock_server.ehlo.side_effect = orig_error

        with patch("smtplib.SMTP", return_value=mock_server), \
             patch("time.sleep") as mock_sleep:
            transport = SyncSMTPTransport()
            with pytest.raises(EmailSendError) as exc_info:
                transport.send(msg, valid_config)

            assert "Failed to transmit email after" in str(exc_info.value)
            assert exc_info.value.__cause__ is orig_error
            assert mock_sleep.call_count == valid_config.max_retries - 1


# ---------------------------------------------------------------------------
# Test Suite 8: Security & Secret Leakage Prevention (Caplog & Exceptions)
# ---------------------------------------------------------------------------
class TestSecurityAndCredentialProtection:
    """Tests ensuring authentication credentials never appear in logs, strings, or exception messages."""

    @pytest.mark.asyncio
    async def test_password_never_in_logs_during_successful_async_send(
        self,
        valid_config: SMTPConfig,
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify SMTP password does not appear in log output during normal operation."""
        msg = build_report_email_message(
            config=valid_config,
            to=["dev@example.com"],
            project_name="LoggingSecurity",
            health_summary=sample_health_summary,
            dashboard_url="https://test.local",
            pdf_data=sample_pdf_bytes,
        )

        mock_smtp = AsyncMock()
        mock_smtp.__aenter__.return_value = mock_smtp

        with patch("aiosmtplib.SMTP", return_value=mock_smtp), caplog.at_level(logging.DEBUG):
            transport = AsyncSMTPTransport()
            await transport.send(msg, valid_config)

            for record in caplog.records:
                assert valid_config.password not in record.message
                assert valid_config.password not in str(record)

    @pytest.mark.asyncio
    async def test_password_never_in_logs_during_failed_async_send(
        self,
        valid_config: SMTPConfig,
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify SMTP password does not appear in log output when transmission fails."""
        msg = build_report_email_message(
            config=valid_config,
            to=["dev@example.com"],
            project_name="LoggingSecurityFail",
            health_summary=sample_health_summary,
            dashboard_url="https://test.local",
            pdf_data=sample_pdf_bytes,
        )

        mock_smtp = AsyncMock()
        mock_smtp.__aenter__.side_effect = aiosmtplib.SMTPException("Relay error")

        with patch("aiosmtplib.SMTP", return_value=mock_smtp), \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             caplog.at_level(logging.DEBUG):
            transport = AsyncSMTPTransport()
            try:
                await transport.send(msg, valid_config)
            except EmailSendError:
                pass

            for record in caplog.records:
                assert valid_config.password not in record.message
                assert valid_config.password not in str(record)

    def test_password_never_in_exception_messages_or_repr(self, valid_env: Dict[str, str]) -> None:
        """Verify password is completely absent from all error messages and exception representations."""
        secret = valid_env["SMTP_PASS"]
        env_copy = dict(valid_env)
        env_copy["SMTP_PORT"] = "not-a-port"

        with pytest.raises(EmailConfigError) as exc_info:
            SMTPConfig.from_env(env_copy)

        err_str = str(exc_info.value)
        err_repr = repr(exc_info.value)
        assert secret not in err_str
        assert secret not in err_repr


# ---------------------------------------------------------------------------
# Test Suite 9: Public API Orchestration (send_report_email & send_report_email_sync)
# ---------------------------------------------------------------------------
class TestPublicAPI:
    """Tests covering end-to-end usage of the high-level public functions and EmailService class."""

    @pytest.mark.asyncio
    async def test_send_report_email_async_full_flow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        valid_env: Dict[str, str],
        sample_health_summary: Dict[str, Any],
        sample_pdf_file: Path,
    ) -> None:
        """Verify public send_report_email() loads config from environment and delivers via aiosmtplib."""
        for k, v in valid_env.items():
            monkeypatch.setenv(k, v)

        mock_smtp = AsyncMock()
        mock_smtp.__aenter__.return_value = mock_smtp

        with patch("aiosmtplib.SMTP", return_value=mock_smtp):
            result = await send_report_email(
                to=["lead@aegis-ai.internal", "vp@aegis-ai.internal"],
                project_name="Aegis-Public-API",
                health_summary=sample_health_summary,
                dashboard_url="https://aegis-ai.internal/dash/public",
                pdf_report=sample_pdf_file,
                pdf_filename="custom_report.pdf",
                cc="cc-user@aegis-ai.internal",
                reply_to="reply@aegis-ai.internal",
            )

            assert result.success is True
            assert result.transport == "aiosmtplib"
            assert "lead@aegis-ai.internal" in result.recipients
            assert "vp@aegis-ai.internal" in result.recipients
            assert "cc-user@aegis-ai.internal" in result.recipients
            mock_smtp.send_message.assert_awaited_once()

    def test_send_report_email_sync_full_flow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        valid_env: Dict[str, str],
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
    ) -> None:
        """Verify public send_report_email_sync() delivers synchronously via smtplib."""
        for k, v in valid_env.items():
            monkeypatch.setenv(k, v)

        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            result = send_report_email_sync(
                to="solo-recipient@company.org",
                project_name="Sync-CLI",
                health_summary=sample_health_summary,
                dashboard_url="https://company.org/dash",
                pdf_report=sample_pdf_bytes,
            )

            assert result.success is True
            assert result.transport == "smtplib"
            assert result.recipients == ["solo-recipient@company.org"]
            mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_report_email_raises_on_missing_config(
        self, monkeypatch: pytest.MonkeyPatch, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify missing environment variables bubble up as EmailConfigError."""
        for key in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"]:
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(EmailConfigError) as exc_info:
            await send_report_email(
                to="dev@test.local",
                project_name="NoConfigProject",
                health_summary=sample_health_summary,
                dashboard_url="https://test.local",
                pdf_report=sample_pdf_bytes,
            )
        assert len(exc_info.value.missing_vars) > 0

    @pytest.mark.asyncio
    async def test_send_report_email_raises_on_validation_failure(
        self,
        valid_config: SMTPConfig,
        sample_health_summary: Dict[str, Any],
        sample_pdf_bytes: bytes,
    ) -> None:
        """Verify invalid recipient email triggers EmailValidationError before any network call."""
        with pytest.raises(EmailValidationError) as exc_info:
            await send_report_email(
                to="invalid-email-address",
                project_name="ValidationTest",
                health_summary=sample_health_summary,
                dashboard_url="https://test.local",
                pdf_report=sample_pdf_bytes,
                config=valid_config,
            )
        assert "Invalid email address format" in str(exc_info.value)

    def test_email_service_class_explicit_injection(
        self, valid_config: SMTPConfig, sample_health_summary: Dict[str, Any], sample_pdf_bytes: bytes
    ) -> None:
        """Verify EmailService class accepts custom mock transports directly via constructor injection."""
        mock_sync = MagicMock()
        mock_sync.send.return_value = EmailSendResult(
            success=True,
            message_id="<test-id@mock>",
            recipients=["inject@test.com"],
            sent_at=time.time(),  # type: ignore
            attempts=1,
            transport="mock_sync",
        )

        service = EmailService(config=valid_config, sync_transport=mock_sync)
        result = service.send_report_sync(
            to="inject@test.com",
            project_name="InjectionTest",
            health_summary=sample_health_summary,
            dashboard_url="https://inject.test",
            pdf_report=sample_pdf_bytes,
        )

        assert result.success is True
        assert result.transport == "mock_sync"
        mock_sync.send.assert_called_once()
