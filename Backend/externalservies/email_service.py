"""
Aegis AI - Email Notification Subsystem.

This module provides enterprise-grade asynchronous and synchronous SMTP dispatch
for project health and risk assessment reports. It compiles rich HTML and plain-text
email bodies from Jinja2 templates, validates inputs against header injection and
malformed data, attaches PDF reports, reads configuration securely from environment
variables, and executes resilient delivery with exponential backoff and structured logging.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import email
from email.message import EmailMessage
import email.utils
import html
import logging
import os
from pathlib import Path
import re
import smtplib
import socket
import ssl
import time
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import urlparse
import uuid

import aiosmtplib
import jinja2

# ---------------------------------------------------------------------------
# Module Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("backend.externalservies.email_service")

# ---------------------------------------------------------------------------
# Constants & Regular Expressions
# ---------------------------------------------------------------------------
DEFAULT_SMTP_PORT: int = 587
DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_BACKOFF_SECONDS: float = 1.0
DEFAULT_MAX_PDF_BYTES: int = 25 * 1024 * 1024  # 25 Megabytes
DEFAULT_PDF_FILENAME: str = "project_health_report.pdf"

_EMAIL_REGEX: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)
_NEWLINE_PATTERN: re.Pattern[str] = re.compile(r"[\r\n]")

# Path to the reporting Jinja2 template directory, relative to this file
_CURRENT_DIR: Path = Path(__file__).resolve().parent
_PROJECT_BACKEND_DIR: Path = _CURRENT_DIR.parent
_DEFAULT_TEMPLATE_DIR: Path = _PROJECT_BACKEND_DIR / "reporting" / "templates"
_DEFAULT_TEMPLATE_NAME: str = "email_report.html"


# ---------------------------------------------------------------------------
# Custom Exception Hierarchy
# ---------------------------------------------------------------------------
class EmailServiceError(Exception):
    """Base exception for all email service failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmailConfigError(EmailServiceError):
    """
    Raised when SMTP configuration is missing, malformed, or invalid.

    Names the exact missing or invalid environment variables without ever
    revealing credential secrets or sensitive connection tokens.
    """

    def __init__(
        self,
        message: str,
        missing_vars: Optional[Sequence[str]] = None,
        invalid_var: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.missing_vars: List[str] = list(missing_vars or [])
        self.invalid_var: Optional[str] = invalid_var


class EmailValidationError(EmailServiceError):
    """
    Raised when recipient lists, email headers, URLs, or attachments fail validation.

    Guards against MIME header injection, illegal URL schemes, empty payloads,
    and oversized files before network operations commence.
    """

    def __init__(self, message: str, field_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.field_name: Optional[str] = field_name


class EmailTemplateError(EmailServiceError):
    """Raised when rendering the Jinja2 email template fails."""

    def __init__(self, message: str, template_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.template_name: Optional[str] = template_name


class EmailSendError(EmailServiceError):
    """
    Raised when SMTP transmission encounters a fatal network, auth, or protocol failure.

    Preserves the underlying original exception as the explicit cause (__cause__).
    """

    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        recipient_count: int = 0,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.host: Optional[str] = host
        self.port: Optional[int] = port
        self.recipient_count: int = recipient_count
        self.attempts: int = attempts


# ---------------------------------------------------------------------------
# Configuration Data Model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SMTPConfig:
    """
    Immutable configuration value object for SMTP transmission.

    All credentials are safe-guarded against accidental logging: __repr__ and __str__
    mask the password field.

    Attributes:
        host: SMTP server hostname or IP address.
        port: SMTP server port (typically 465 for SSL/TLS, 587 for STARTTLS, 25 for local relay).
        user: Authentication username (typically an email address or API key).
        password: Authentication credential (kept confidential).
        from_address: Sender envelope and header address (defaults to user or SMTP_FROM).
        use_tls: When True, initiates connection immediately with TLS/SSL (implicit TLS, port 465).
        start_tls: When True, upgrades clear-text connection to TLS via STARTTLS command.
        timeout: Socket connection and operation timeout in seconds.
        max_retries: Number of connection/send retry attempts on transient network faults.
        retry_backoff: Base multiplier for exponential backoff between retries.
        max_pdf_bytes: Upper limit on allowable PDF attachment byte size.
    """

    host: str
    port: int
    user: str
    password: str
    from_address: str
    use_tls: bool = False
    start_tls: bool = True
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff: float = DEFAULT_RETRY_BACKOFF_SECONDS
    max_pdf_bytes: int = DEFAULT_MAX_PDF_BYTES

    def __repr__(self) -> str:
        """Confidential representation masking password to prevent leakage in loggers."""
        return (
            f"SMTPConfig(host={self.host!r}, port={self.port}, "
            f"user={self.user!r}, password='***', from_address={self.from_address!r}, "
            f"use_tls={self.use_tls}, start_tls={self.start_tls}, timeout={self.timeout}, "
            f"max_retries={self.max_retries})"
        )

    def __str__(self) -> str:
        """Confidential string representation masking password."""
        return self.__repr__()

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
        override_from: Optional[str] = None,
    ) -> "SMTPConfig":
        """
        Instantiate and validate SMTP configuration safely from environment variables.

        Required Environment Variables:
            - SMTP_HOST: Hostname of the SMTP server.
            - SMTP_PORT: Port number (1-65535).
            - SMTP_USER: Username for SMTP authentication.
            - SMTP_PASS: Password or secret token for SMTP authentication.

        Optional Environment Variables:
            - SMTP_FROM: Default sender address (falls back to SMTP_USER if unset).
            - SMTP_TIMEOUT: Operation timeout in seconds (default: 30.0).
            - SMTP_MAX_RETRIES: Maximum retry count (default: 3).
            - SMTP_RETRY_BACKOFF: Backoff factor in seconds (default: 1.0).
            - SMTP_USE_TLS: Explicit override ("true"/"false") for implicit TLS.
            - SMTP_START_TLS: Explicit override ("true"/"false") for STARTTLS.
            - SMTP_MAX_PDF_BYTES: Max size in bytes for PDF attachments (default: 25MB).

        Args:
            env: Optional dictionary of environment variables. If None, os.environ is used.
            override_from: Optional sender address override.

        Returns:
            Validated SMTPConfig instance.

        Raises:
            EmailConfigError: If required variables are missing or values are malformed.
        """
        source = env if env is not None else os.environ

        missing: List[str] = []
        raw_host = source.get("SMTP_HOST", "").strip() if "SMTP_HOST" in source else ""
        raw_user = source.get("SMTP_USER", "").strip() if "SMTP_USER" in source else ""
        raw_pass = source.get("SMTP_PASS", "")
        if not raw_pass and "SMTP_PASSWORD" in source:
            raw_pass = source.get("SMTP_PASSWORD", "")

        if not raw_host:
            missing.append("SMTP_HOST")
        if "SMTP_PORT" not in source:
            missing.append("SMTP_PORT")
        if not raw_user:
            missing.append("SMTP_USER")
        if not raw_pass:
            missing.append("SMTP_PASS")

        if missing:
            raise EmailConfigError(
                f"Missing required SMTP environment variable(s): {', '.join(sorted(missing))}",
                missing_vars=sorted(missing),
            )

        raw_port = str(source.get("SMTP_PORT", ""))
        # Parse and validate port
        try:
            port = int(raw_port.strip())
        except ValueError:
            raise EmailConfigError(
                f"Invalid SMTP_PORT: '{raw_port}' is not a valid integer.",
                invalid_var="SMTP_PORT",
            )

        if port < 1 or port > 65535:
            raise EmailConfigError(
                f"Invalid SMTP_PORT: {port} is out of allowable range (1-65535).",
                invalid_var="SMTP_PORT",
            )

        # Sensible TLS auto-selection:
        # Port 465 is the standard for implicit SSL/TLS (SMTPS).
        # Ports 587 and 25 use explicit STARTTLS.
        if port == 465:
            auto_use_tls = True
            auto_start_tls = False
        else:
            auto_use_tls = False
            auto_start_tls = True

        # Allow explicit environment overrides if present
        if "SMTP_USE_TLS" in source:
            use_tls = source["SMTP_USE_TLS"].strip().lower() in ("true", "1", "yes")
        else:
            use_tls = auto_use_tls

        if "SMTP_START_TLS" in source:
            start_tls = source["SMTP_START_TLS"].strip().lower() in ("true", "1", "yes")
        else:
            start_tls = auto_start_tls

        # Parse timeout
        timeout = DEFAULT_TIMEOUT_SECONDS
        if "SMTP_TIMEOUT" in source:
            try:
                parsed_timeout = float(source["SMTP_TIMEOUT"].strip())
                if parsed_timeout > 0:
                    timeout = parsed_timeout
            except ValueError:
                logger.warning("Invalid SMTP_TIMEOUT in environment; using default %s", timeout)

        # Parse max retries
        max_retries = DEFAULT_MAX_RETRIES
        if "SMTP_MAX_RETRIES" in source:
            try:
                parsed_retries = int(source["SMTP_MAX_RETRIES"].strip())
                if parsed_retries >= 0:
                    max_retries = parsed_retries
            except ValueError:
                logger.warning("Invalid SMTP_MAX_RETRIES in environment; using default %s", max_retries)

        # Parse max PDF bytes
        max_pdf_bytes = DEFAULT_MAX_PDF_BYTES
        if "SMTP_MAX_PDF_BYTES" in source:
            try:
                parsed_bytes = int(source["SMTP_MAX_PDF_BYTES"].strip())
                if parsed_bytes > 0:
                    max_pdf_bytes = parsed_bytes
            except ValueError:
                logger.warning("Invalid SMTP_MAX_PDF_BYTES in environment; using default %s", max_pdf_bytes)

        # Determine sender address
        raw_from = override_from or source.get("SMTP_FROM", "").strip() or raw_user

        return cls(
            host=raw_host,
            port=port,
            user=raw_user,
            password=raw_pass,
            from_address=raw_from,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=DEFAULT_RETRY_BACKOFF_SECONDS,
            max_pdf_bytes=max_pdf_bytes,
        )


# ---------------------------------------------------------------------------
# Send Result Data Model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EmailSendResult:
    """
    Structured outcome metadata returned upon email dispatch completion.

    Attributes:
        success: Whether the message was successfully handed off to the SMTP relay.
        message_id: Generated or received unique message identifier.
        recipients: Full list of intended delivery addresses (To + CC + BCC).
        sent_at: UTC timestamp when transmission concluded.
        attempts: Number of connection attempts executed.
        transport: Transport mechanism used ('aiosmtplib' or 'smtplib').
        error_message: Detailed error string if transmission failed.
    """

    success: bool
    message_id: str
    recipients: List[str]
    sent_at: datetime
    attempts: int
    transport: str
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Input Validation & Sanitization Helpers
# ---------------------------------------------------------------------------
def validate_header_field(value: str, field_name: str) -> str:
    """
    Verify that an email header value contains no carriage return or newline characters.

    This prevents Header Injection / SMTP splitting attacks where malicious actors
    inject additional headers (e.g. BCC, Subject) via unsanitized input.

    Args:
        value: Header string to validate.
        field_name: Descriptive name of the header field for error reporting.

    Returns:
        Stripped header string.

    Raises:
        EmailValidationError: If newlines or carriage returns are found.
    """
    if not isinstance(value, str):
        raise EmailValidationError(
            f"Header field '{field_name}' must be a string, got {type(value).__name__}.",
            field_name=field_name,
        )
    if _NEWLINE_PATTERN.search(value):
        raise EmailValidationError(
            f"Header injection detected in '{field_name}': newline characters are prohibited.",
            field_name=field_name,
        )
    return value.strip()


def validate_email_address(email_addr: str, field_name: str = "recipient") -> str:
    """
    Validate an individual email address for RFC compliance and injection safety.

    Args:
        email_addr: Email address string to validate.
        field_name: Originating field identifier for diagnostic context.

    Returns:
        Normalized, lowercased email string.

    Raises:
        EmailValidationError: If the address is empty, malformed, or contains invalid characters.
    """
    cleaned = validate_header_field(email_addr, field_name)
    if not cleaned:
        raise EmailValidationError(
            f"Email address in '{field_name}' cannot be empty.",
            field_name=field_name,
        )
    if not _EMAIL_REGEX.match(cleaned):
        raise EmailValidationError(
            f"Invalid email address format in '{field_name}': '{cleaned}'.",
            field_name=field_name,
        )
    return cleaned


def normalize_and_validate_recipients(
    recipients: Union[str, Iterable[str], None],
    field_name: str = "to",
    allow_empty: bool = False,
) -> List[str]:
    """
    Normalize recipient inputs into a validated, unique list of email addresses.

    Accepts a single email string or an iterable of strings.

    Args:
        recipients: Email string, sequence of strings, or None.
        field_name: Name of the recipient field ('to', 'cc', 'bcc').
        allow_empty: If False, empty recipient collections raise an error.

    Returns:
        List of validated email address strings.

    Raises:
        EmailValidationError: If validation fails or the collection is unexpectedly empty.
    """
    if recipients is None:
        if allow_empty:
            return []
        raise EmailValidationError(
            f"Recipient list for '{field_name}' cannot be None.",
            field_name=field_name,
        )

    raw_list: List[str] = []
    if isinstance(recipients, str):
        # Support comma-separated strings as well as single addresses
        parts = [p.strip() for p in recipients.split(",") if p.strip()]
        raw_list.extend(parts)
    elif isinstance(recipients, Iterable):
        for item in recipients:
            if not isinstance(item, str):
                raise EmailValidationError(
                    f"All items in '{field_name}' must be strings, found {type(item).__name__}.",
                    field_name=field_name,
                )
            if item.strip():
                raw_list.append(item.strip())
    else:
        raise EmailValidationError(
            f"Unsupported type for '{field_name}': {type(recipients).__name__}.",
            field_name=field_name,
        )

    if not raw_list and not allow_empty:
        raise EmailValidationError(
            f"At least one valid recipient must be provided for '{field_name}'.",
            field_name=field_name,
        )

    validated: List[str] = []
    seen: set[str] = set()
    for addr in raw_list:
        valid_addr = validate_email_address(addr, field_name=field_name)
        if valid_addr not in seen:
            seen.add(valid_addr)
            validated.append(valid_addr)

    return validated


def validate_dashboard_url(url: str) -> str:
    """
    Validate that the provided dashboard URL is an absolute HTTP/HTTPS address.

    Rejects dangerous schemes like javascript:, data:, file:, and relative URLs.

    Args:
        url: URL string to inspect.

    Returns:
        Validated, stripped URL string.

    Raises:
        EmailValidationError: If the URL is empty, contains newlines, or lacks a valid scheme/domain.
    """
    cleaned = validate_header_field(url, "dashboard_url")
    if not cleaned:
        raise EmailValidationError(
            "dashboard_url cannot be empty.",
            field_name="dashboard_url",
        )

    try:
        parsed = urlparse(cleaned)
    except Exception as exc:
        raise EmailValidationError(
            f"Malformed dashboard_url: '{cleaned}' ({exc}).",
            field_name="dashboard_url",
        ) from exc

    if parsed.scheme.lower() not in ("http", "https"):
        raise EmailValidationError(
            f"Invalid scheme in dashboard_url: '{parsed.scheme}'. Only 'http' and 'https' are allowed.",
            field_name="dashboard_url",
        )

    if not parsed.netloc:
        raise EmailValidationError(
            f"dashboard_url lacks a valid hostname/netloc: '{cleaned}'.",
            field_name="dashboard_url",
        )

    return cleaned


def validate_and_read_pdf(
    pdf_report: Union[bytes, str, Path],
    max_size_bytes: int = DEFAULT_MAX_PDF_BYTES,
) -> Tuple[bytes, int]:
    """
    Validate and extract raw bytes from a PDF report payload.

    Supports in-memory bytes, string paths, and pathlib.Path objects.

    Args:
        pdf_report: Raw bytes or filesystem path pointing to the generated PDF.
        max_size_bytes: Maximum allowed size in bytes (default: 25MB).

    Returns:
        Tuple of (raw_bytes, byte_length).

    Raises:
        EmailValidationError: If file does not exist, is empty, exceeds size limit, or is not a PDF.
    """
    if isinstance(pdf_report, bytes):
        payload = pdf_report
    elif isinstance(pdf_report, (str, Path)):
        path_obj = Path(pdf_report).resolve()
        if not path_obj.exists():
            raise EmailValidationError(
                f"PDF report file not found at path: {path_obj}",
                field_name="pdf_report",
            )
        if not path_obj.is_file():
            raise EmailValidationError(
                f"PDF report path is not a regular file: {path_obj}",
                field_name="pdf_report",
            )
        try:
            payload = path_obj.read_bytes()
        except OSError as exc:
            raise EmailValidationError(
                f"Failed to read PDF file at {path_obj}: {exc}",
                field_name="pdf_report",
            ) from exc
    else:
        raise EmailValidationError(
            f"pdf_report must be bytes or a filesystem Path, got {type(pdf_report).__name__}.",
            field_name="pdf_report",
        )

    size = len(payload)
    if size == 0:
        raise EmailValidationError(
            "PDF report is empty (0 bytes). Cannot attach an empty report.",
            field_name="pdf_report",
        )

    if size > max_size_bytes:
        raise EmailValidationError(
            f"PDF report size ({size} bytes) exceeds maximum allowable limit of {max_size_bytes} bytes.",
            field_name="pdf_report",
        )

    # Validate PDF signature magic bytes (%PDF-)
    if not payload.startswith(b"%PDF-"):
        logger.warning(
            "PDF report does not begin with standard %%PDF- magic bytes; proceeding with caution."
        )

    return payload, size


# ---------------------------------------------------------------------------
# Template Renderer
# ---------------------------------------------------------------------------
class EmailTemplateRenderer:
    """
    Jinja2 template renderer with autoescape protection and isolated directory loading.

    Renders rich HTML executive health briefings from templates loaded relative to the
    project source tree rather than the current working directory.
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        template_name: str = _DEFAULT_TEMPLATE_NAME,
    ) -> None:
        """
        Initialize the template rendering environment.

        Args:
            template_dir: Filesystem directory containing templates. Defaults to
                          Backend/reporting/templates.
            template_name: Primary template filename (default: 'email_report.html').
        """
        self.template_dir: Path = (
            Path(template_dir).resolve() if template_dir else _DEFAULT_TEMPLATE_DIR
        )
        self.template_name: str = template_name

        if not self.template_dir.exists():
            logger.warning(
                "Template directory does not exist: %s; template rendering may fail.",
                self.template_dir,
            )

        self._env: jinja2.Environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        project_name: str,
        health_summary: Mapping[str, Any],
        dashboard_url: str,
        pdf_filename: str = DEFAULT_PDF_FILENAME,
        report_date: Optional[str] = None,
    ) -> str:
        """
        Compile the HTML email body from the Jinja2 template.

        Args:
            project_name: Display name of the software project/repository.
            health_summary: Dictionary containing health scores, status, metrics, and risks.
            dashboard_url: Clickable URL to the interactive web dashboard.
            pdf_filename: Human-readable filename of the attached PDF.
            report_date: Optional display date string (e.g. '2026-11-19 UTC').

        Returns:
            Rendered HTML string.

        Raises:
            EmailTemplateError: If template loading or compilation fails.
        """
        if not report_date:
            report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        context: Dict[str, Any] = {
            "project_name": project_name,
            "health_summary": health_summary or {},
            "dashboard_url": dashboard_url,
            "pdf_filename": pdf_filename,
            "report_date": report_date,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        try:
            template = self._env.get_template(self.template_name)
            return template.render(context)
        except jinja2.TemplateNotFound as exc:
            raise EmailTemplateError(
                f"Template '{self.template_name}' not found in directory: {self.template_dir}",
                template_name=self.template_name,
            ) from exc
        except jinja2.TemplateError as exc:
            raise EmailTemplateError(
                f"Failed to render email template '{self.template_name}': {exc}",
                template_name=self.template_name,
            ) from exc


# ---------------------------------------------------------------------------
# Plain-Text Fallback Builder
# ---------------------------------------------------------------------------
def build_plain_text_body(
    project_name: str,
    health_summary: Mapping[str, Any],
    dashboard_url: str,
    pdf_filename: str = DEFAULT_PDF_FILENAME,
) -> str:
    """
    Construct a clean, structured plain-text fallback representation of the report.

    Provides high readability for text-only email clients, screen readers, and low-bandwidth
    environments while retaining full executive assessment details and direct dashboard links.

    Args:
        project_name: Name of the repository/project.
        health_summary: Data dictionary containing status, scores, metrics, and risks.
        dashboard_url: Full URL to the interactive dashboard.
        pdf_filename: Name of the attached PDF report.

    Returns:
        Formatted multi-line plain text string.
    """
    summary = health_summary or {}
    raw_status = (
        summary.get("status")
        or summary.get("health_status")
        or "UNKNOWN"
    )
    status_str = str(raw_status).upper()

    score_val = summary.get("health_score")
    if score_val is None:
        score_val = summary.get("score")
    if isinstance(score_val, (int, float)):
        score_display = f"{score_val:.1f}/100"
    else:
        score_display = "N/A"

    risk_level = str(
        summary.get("risk_level")
        or summary.get("risk")
        or "MODERATE"
    ).upper()

    exec_summary = (
        summary.get("executive_summary")
        or summary.get("summary_statement")
        or summary.get("summary")
        or "No executive summary statement provided for this evaluation period."
    )

    lines: List[str] = [
        "================================================================================",
        "कVaच (KAVACH) - SOFTWARE PROJECT HEALTH & RISK INTELLIGENCE REPORT",
        "================================================================================",
        f"Project:      {project_name}",
        f"Status:       {status_str}",
        f"Health Score: {score_display}",
        f"Risk Level:   {risk_level}",
        f"Generated At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "--------------------------------------------------------------------------------",
        "",
        "EXECUTIVE OVERVIEW:",
        f"{exec_summary}",
        "",
    ]

    # Metrics section
    metrics = summary.get("metrics")
    if isinstance(metrics, dict) and metrics:
        lines.append("KEY TELEMETRY METRICS:")
        for key, val in metrics.items():
            label = key.replace("_", " ").title()
            lines.append(f"  * {label}: {val}")
        lines.append("")

    # Top Active Risks
    risks = (
        summary.get("active_risks")
        or summary.get("risks")
        or summary.get("active_flags")
        or []
    )
    if isinstance(risks, list) and risks:
        lines.append(f"ACTIVE RISKS & BOTTLENECKS ({len(risks)} detected):")
        for item in risks:
            if isinstance(item, dict):
                sev = str(item.get("severity") or item.get("level") or "INFO").upper()
                title = item.get("title") or item.get("type") or item.get("name") or "Risk"
                msg = item.get("message") or item.get("description") or ""
                lines.append(f"  [{sev}] {title}: {msg}")
                if item.get("impact"):
                    lines.append(f"         Impact: {item.get('impact')}")
            else:
                lines.append(f"  * {item}")
        lines.append("")
    else:
        lines.append("ACTIVE RISKS & BOTTLENECKS:")
        lines.append("  No critical active risk indicators recorded for this cycle.")
        lines.append("")

    # Recommendations
    recs = summary.get("recommendations") or summary.get("action_items") or []
    if isinstance(recs, list) and recs:
        lines.append("RECOMMENDED ACTIONS:")
        for rec in recs:
            if isinstance(rec, dict):
                action = rec.get("action") or rec.get("title") or "Action"
                detail = rec.get("detail") or rec.get("description") or ""
                lines.append(f"  * {action}: {detail}")
            else:
                lines.append(f"  * {rec}")
        lines.append("")

    # Dashboard and Attachment Links
    lines.extend([
        "--------------------------------------------------------------------------------",
        "ACCESS INTERACTIVE DASHBOARD:",
        f"{dashboard_url}",
        "",
        "ATTACHMENT NOTICE:",
        f"A comprehensive PDF report ({pdf_filename}) is attached to this email.",
        "--------------------------------------------------------------------------------",
        "Automated notification sent by कVaच (Kavach) Subsystem. Confidential.",
        "================================================================================",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MIME Message Builder
# ---------------------------------------------------------------------------
def build_report_email_message(
    config: SMTPConfig,
    to: Sequence[str],
    project_name: str,
    health_summary: Mapping[str, Any],
    dashboard_url: str,
    pdf_data: bytes,
    pdf_filename: str = DEFAULT_PDF_FILENAME,
    cc: Optional[Sequence[str]] = None,
    bcc: Optional[Sequence[str]] = None,
    reply_to: Optional[str] = None,
    subject_override: Optional[str] = None,
    template_renderer: Optional[EmailTemplateRenderer] = None,
) -> EmailMessage:
    """
    Construct a complete, multi-part MIME EmailMessage with HTML, plain-text, and PDF attachment.

    Structure:
        multipart/mixed
        ├── multipart/alternative
        │   ├── text/plain (Fallback ASCII overview)
        │   └── text/html  (Rich Jinja2 compiled executive briefing)
        └── application/pdf (Attached project report)

    Args:
        config: Validated SMTP configuration.
        to: Sequence of validated recipient email addresses.
        project_name: Name of the project/repository.
        health_summary: Health and risk metadata.
        dashboard_url: Web dashboard URL.
        pdf_data: Raw byte content of the PDF report.
        pdf_filename: Filename assigned to the attachment.
        cc: Optional sequence of CC recipient addresses.
        bcc: Optional sequence of BCC recipient addresses.
        reply_to: Optional Reply-To address.
        subject_override: Optional custom subject line.
        template_renderer: Optional custom template renderer instance.

    Returns:
        Configured email.message.EmailMessage object ready for transmission.
    """
    clean_project = validate_header_field(project_name, "project_name")
    clean_dash_url = validate_dashboard_url(dashboard_url)
    clean_pdf_filename = validate_header_field(pdf_filename, "pdf_filename") or DEFAULT_PDF_FILENAME

    # Determine status and score for subject line
    summary = health_summary or {}
    status_label = str(summary.get("status") or summary.get("health_status") or "Health Briefing").upper()
    score_val = summary.get("health_score") or summary.get("score")
    score_str = f"{score_val:.1f}/100" if isinstance(score_val, (int, float)) else ""
    score_part = f" ({score_str})" if score_str else ""

    if subject_override:
        subject = validate_header_field(subject_override, "subject_override")
    else:
        subject = f"[Aegis AI] Health Report: {clean_project} - {status_label}{score_part}"

    # Build plain text body
    plain_text = build_plain_text_body(
        project_name=clean_project,
        health_summary=summary,
        dashboard_url=clean_dash_url,
        pdf_filename=clean_pdf_filename,
    )

    # Render HTML body
    renderer = template_renderer or EmailTemplateRenderer()
    html_content = renderer.render(
        project_name=clean_project,
        health_summary=summary,
        dashboard_url=clean_dash_url,
        pdf_filename=clean_pdf_filename,
    )

    # Initialize EmailMessage (RFC 5322)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.from_address
    msg["To"] = ", ".join(to)

    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    if reply_to:
        clean_reply_to = validate_email_address(reply_to, "reply_to")
        msg["Reply-To"] = clean_reply_to

    msg["Date"] = email.utils.formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=config.host.split(":")[-1])

    # Set content with plain text fallback
    msg.set_content(plain_text, subtype="plain", charset="utf-8")

    # Add HTML alternative part
    msg.add_alternative(html_content, subtype="html", charset="utf-8")

    # Attach PDF report
    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename=clean_pdf_filename,
    )

    return msg


# ---------------------------------------------------------------------------
# Transport Implementations (Isolated for Testing & Mocking)
# ---------------------------------------------------------------------------
class AsyncSMTPTransport:
    """
    Asynchronous SMTP transport wrapper utilizing aiosmtplib.

    Encapsulates connection lifecycle, TLS negotiation, authentication,
    and retry loops with exponential backoff.
    """

    def __init__(self) -> None:
        pass

    async def send(
        self,
        message: EmailMessage,
        config: SMTPConfig,
    ) -> EmailSendResult:
        """
        Dispatch the EmailMessage asynchronously over SMTP with retry and backoff.

        Args:
            message: Constructed EmailMessage to transmit.
            config: SMTP connection and authentication configuration.

        Returns:
            EmailSendResult metadata on success.

        Raises:
            EmailSendError: If all retries fail or a non-recoverable error occurs.
        """
        recipients = [addr.strip() for addr in message.get("To", "").split(",") if addr.strip()]
        if "Cc" in message:
            recipients.extend([addr.strip() for addr in message.get("Cc", "").split(",") if addr.strip()])
        if "Bcc" in message:
            recipients.extend([addr.strip() for addr in message.get("Bcc", "").split(",") if addr.strip()])

        last_error: Optional[Exception] = None
        attempt = 0
        total_attempts = max(1, config.max_retries)

        logger.info(
            "Initiating async SMTP transmission to host=%s:%d for %d recipient(s) (use_tls=%s, start_tls=%s)",
            config.host,
            config.port,
            len(recipients),
            config.use_tls,
            config.start_tls,
        )

        for attempt in range(1, total_attempts + 1):
            try:
                # Prepare aiosmtplib client with sensible timeout
                client = aiosmtplib.SMTP(
                    hostname=config.host,
                    port=config.port,
                    use_tls=config.use_tls,
                    start_tls=config.start_tls,
                    timeout=config.timeout,
                )

                async with client:
                    if config.user and config.password:
                        await client.login(config.user, config.password)
                    await client.send_message(message)

                logger.info(
                    "Async email successfully dispatched on attempt %d/%d to %s",
                    attempt,
                    total_attempts,
                    recipients,
                )
                return EmailSendResult(
                    success=True,
                    message_id=message.get("Message-ID", ""),
                    recipients=recipients,
                    sent_at=datetime.now(timezone.utc),
                    attempts=attempt,
                    transport="aiosmtplib",
                )

            except (
                aiosmtplib.SMTPException,
                socket.gaierror,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as exc:
                last_error = exc
                logger.warning(
                    "Async SMTP attempt %d/%d to %s:%d failed: %s",
                    attempt,
                    total_attempts,
                    config.host,
                    config.port,
                    exc,
                )
                if attempt < total_attempts:
                    sleep_duration = config.retry_backoff * (2 ** (attempt - 1))
                    await asyncio.sleep(sleep_duration)

            except Exception as exc:
                # Non-transient or unexpected error - fail immediately
                logger.error(
                    "Fatal unrecoverable error during async SMTP dispatch: %s",
                    exc,
                    exc_info=True,
                )
                raise EmailSendError(
                    f"Fatal async SMTP error to {config.host}:{config.port}: {exc}",
                    host=config.host,
                    port=config.port,
                    recipient_count=len(recipients),
                    attempts=attempt,
                ) from exc

        # All retries exhausted
        raise EmailSendError(
            f"Failed to transmit email after {total_attempts} attempt(s) to {config.host}:{config.port}: {last_error}",
            host=config.host,
            port=config.port,
            recipient_count=len(recipients),
            attempts=total_attempts,
        ) from last_error


class SyncSMTPTransport:
    """
    Synchronous SMTP transport wrapper utilizing standard library smtplib.

    Supports both SMTPS (port 465) and STARTTLS (port 587/25) connections
    with retry handling.
    """

    def __init__(self) -> None:
        pass

    def send(
        self,
        message: EmailMessage,
        config: SMTPConfig,
    ) -> EmailSendResult:
        """
        Dispatch the EmailMessage synchronously over SMTP with retry and backoff.

        Args:
            message: Constructed EmailMessage to transmit.
            config: SMTP connection and authentication configuration.

        Returns:
            EmailSendResult metadata on success.

        Raises:
            EmailSendError: If all retries fail or a fatal exception occurs.
        """
        recipients = [addr.strip() for addr in message.get("To", "").split(",") if addr.strip()]
        if "Cc" in message:
            recipients.extend([addr.strip() for addr in message.get("Cc", "").split(",") if addr.strip()])
        if "Bcc" in message:
            recipients.extend([addr.strip() for addr in message.get("Bcc", "").split(",") if addr.strip()])

        last_error: Optional[Exception] = None
        attempt = 0
        total_attempts = max(1, config.max_retries)

        logger.info(
            "Initiating sync SMTP transmission to host=%s:%d for %d recipient(s) (use_tls=%s, start_tls=%s)",
            config.host,
            config.port,
            len(recipients),
            config.use_tls,
            config.start_tls,
        )

        for attempt in range(1, total_attempts + 1):
            server: Optional[Union[smtplib.SMTP_SSL, smtplib.SMTP]] = None
            try:
                if config.use_tls:
                    server = smtplib.SMTP_SSL(
                        host=config.host,
                        port=config.port,
                        timeout=config.timeout,
                    )
                else:
                    server = smtplib.SMTP(
                        host=config.host,
                        port=config.port,
                        timeout=config.timeout,
                    )

                server.ehlo()

                if config.start_tls and not config.use_tls:
                    server.starttls()
                    server.ehlo()

                if config.user and config.password:
                    server.login(config.user, config.password)

                server.send_message(message)
                server.quit()
                server = None

                logger.info(
                    "Sync email successfully dispatched on attempt %d/%d to %s",
                    attempt,
                    total_attempts,
                    recipients,
                )
                return EmailSendResult(
                    success=True,
                    message_id=message.get("Message-ID", ""),
                    recipients=recipients,
                    sent_at=datetime.now(timezone.utc),
                    attempts=attempt,
                    transport="smtplib",
                )

            except (
                smtplib.SMTPException,
                socket.gaierror,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as exc:
                last_error = exc
                logger.warning(
                    "Sync SMTP attempt %d/%d to %s:%d failed: %s",
                    attempt,
                    total_attempts,
                    config.host,
                    config.port,
                    exc,
                )
                if attempt < total_attempts:
                    sleep_duration = config.retry_backoff * (2 ** (attempt - 1))
                    time.sleep(sleep_duration)

            except Exception as exc:
                logger.error(
                    "Fatal unrecoverable error during sync SMTP dispatch: %s",
                    exc,
                    exc_info=True,
                )
                raise EmailSendError(
                    f"Fatal sync SMTP error to {config.host}:{config.port}: {exc}",
                    host=config.host,
                    port=config.port,
                    recipient_count=len(recipients),
                    attempts=attempt,
                ) from exc

            finally:
                if server is not None:
                    try:
                        server.close()
                    except Exception:
                        pass

        # All retries exhausted
        raise EmailSendError(
            f"Failed to transmit email after {total_attempts} attempt(s) to {config.host}:{config.port}: {last_error}",
            host=config.host,
            port=config.port,
            recipient_count=len(recipients),
            attempts=total_attempts,
        ) from last_error


# ---------------------------------------------------------------------------
# Email Service Class
# ---------------------------------------------------------------------------
class EmailService:
    """
    Comprehensive email service orchestrator for project health report delivery.

    Coordinates input validation, template compilation, MIME message generation,
    and multi-transport dispatch (async/sync) with safe environment resolution.
    """

    def __init__(
        self,
        config: Optional[SMTPConfig] = None,
        async_transport: Optional[AsyncSMTPTransport] = None,
        sync_transport: Optional[SyncSMTPTransport] = None,
        template_renderer: Optional[EmailTemplateRenderer] = None,
    ) -> None:
        """
        Initialize the EmailService.

        Args:
            config: Optional pre-configured SMTPConfig. If None, loaded lazily from env.
            async_transport: Optional custom async transport for dependency injection/testing.
            sync_transport: Optional custom sync transport for dependency injection/testing.
            template_renderer: Optional custom template renderer.
        """
        self._config: Optional[SMTPConfig] = config
        self._async_transport: AsyncSMTPTransport = async_transport or AsyncSMTPTransport()
        self._sync_transport: SyncSMTPTransport = sync_transport or SyncSMTPTransport()
        self._renderer: EmailTemplateRenderer = template_renderer or EmailTemplateRenderer()

    def get_config(self) -> SMTPConfig:
        """Retrieve the active configuration or resolve it from environment variables."""
        if self._config is None:
            self._config = SMTPConfig.from_env()
        return self._config

    def build_message(
        self,
        to: Union[str, Sequence[str]],
        project_name: str,
        health_summary: Mapping[str, Any],
        dashboard_url: str,
        pdf_report: Union[bytes, str, Path],
        pdf_filename: str = DEFAULT_PDF_FILENAME,
        cc: Optional[Union[str, Sequence[str]]] = None,
        bcc: Optional[Union[str, Sequence[str]]] = None,
        reply_to: Optional[str] = None,
        subject_override: Optional[str] = None,
        config: Optional[SMTPConfig] = None,
    ) -> EmailMessage:
        """
        Validate inputs and construct the RFC 5322 MIME EmailMessage.

        Args:
            to: Recipient email address or sequence of addresses.
            project_name: Name of the repository/project.
            health_summary: Telemetry assessment dictionary.
            dashboard_url: Absolute URL to the web dashboard.
            pdf_report: PDF report raw bytes or filesystem path.
            pdf_filename: Filename assigned to attachment.
            cc: Optional CC recipient(s).
            bcc: Optional BCC recipient(s).
            reply_to: Optional Reply-To address.
            subject_override: Optional custom email subject.
            config: Optional config override.

        Returns:
            Fully compiled EmailMessage.

        Raises:
            EmailValidationError: If inputs are invalid or missing.
            EmailTemplateError: If template rendering fails.
        """
        active_config = config or self.get_config()

        validated_to = normalize_and_validate_recipients(to, field_name="to", allow_empty=False)
        validated_cc = normalize_and_validate_recipients(cc, field_name="cc", allow_empty=True)
        validated_bcc = normalize_and_validate_recipients(bcc, field_name="bcc", allow_empty=True)

        pdf_bytes, _ = validate_and_read_pdf(pdf_report, max_size_bytes=active_config.max_pdf_bytes)

        return build_report_email_message(
            config=active_config,
            to=validated_to,
            project_name=project_name,
            health_summary=health_summary,
            dashboard_url=dashboard_url,
            pdf_data=pdf_bytes,
            pdf_filename=pdf_filename,
            cc=validated_cc if validated_cc else None,
            bcc=validated_bcc if validated_bcc else None,
            reply_to=reply_to,
            subject_override=subject_override,
            template_renderer=self._renderer,
        )

    async def send_report(
        self,
        to: Union[str, Sequence[str]],
        project_name: str,
        health_summary: Mapping[str, Any],
        dashboard_url: str,
        pdf_report: Union[bytes, str, Path],
        pdf_filename: str = DEFAULT_PDF_FILENAME,
        cc: Optional[Union[str, Sequence[str]]] = None,
        bcc: Optional[Union[str, Sequence[str]]] = None,
        reply_to: Optional[str] = None,
        subject_override: Optional[str] = None,
        config: Optional[SMTPConfig] = None,
    ) -> EmailSendResult:
        """
        Build and dispatch an executive health report email asynchronously.

        Args:
            to: Destination recipient email address or sequence of addresses.
            project_name: Target project/repository name.
            health_summary: Telemetry metrics, health status, and risk flags.
            dashboard_url: Web dashboard URL.
            pdf_report: PDF bytes or file path.
            pdf_filename: Name of the attached PDF file.
            cc: Optional CC recipient(s).
            bcc: Optional BCC recipient(s).
            reply_to: Optional Reply-To address.
            subject_override: Optional subject line override.
            config: Optional SMTP configuration override.

        Returns:
            EmailSendResult containing delivery status and attempt count.

        Raises:
            EmailConfigError: If configuration is invalid.
            EmailValidationError: If inputs fail validation checks.
            EmailSendError: If delivery fails after retries.
        """
        active_config = config or self.get_config()
        message = self.build_message(
            to=to,
            project_name=project_name,
            health_summary=health_summary,
            dashboard_url=dashboard_url,
            pdf_report=pdf_report,
            pdf_filename=pdf_filename,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            subject_override=subject_override,
            config=active_config,
        )
        return await self._async_transport.send(message, active_config)

    def send_report_sync(
        self,
        to: Union[str, Sequence[str]],
        project_name: str,
        health_summary: Mapping[str, Any],
        dashboard_url: str,
        pdf_report: Union[bytes, str, Path],
        pdf_filename: str = DEFAULT_PDF_FILENAME,
        cc: Optional[Union[str, Sequence[str]]] = None,
        bcc: Optional[Union[str, Sequence[str]]] = None,
        reply_to: Optional[str] = None,
        subject_override: Optional[str] = None,
        config: Optional[SMTPConfig] = None,
    ) -> EmailSendResult:
        """
        Build and dispatch an executive health report email synchronously.

        Args:
            to: Destination recipient email address or sequence of addresses.
            project_name: Target project/repository name.
            health_summary: Telemetry metrics, health status, and risk flags.
            dashboard_url: Web dashboard URL.
            pdf_report: PDF bytes or file path.
            pdf_filename: Name of the attached PDF file.
            cc: Optional CC recipient(s).
            bcc: Optional BCC recipient(s).
            reply_to: Optional Reply-To address.
            subject_override: Optional subject line override.
            config: Optional SMTP configuration override.

        Returns:
            EmailSendResult containing delivery status and attempt count.

        Raises:
            EmailConfigError: If configuration is invalid.
            EmailValidationError: If inputs fail validation checks.
            EmailSendError: If delivery fails after retries.
        """
        active_config = config or self.get_config()
        message = self.build_message(
            to=to,
            project_name=project_name,
            health_summary=health_summary,
            dashboard_url=dashboard_url,
            pdf_report=pdf_report,
            pdf_filename=pdf_filename,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            subject_override=subject_override,
            config=active_config,
        )
        return self._sync_transport.send(message, active_config)


# ---------------------------------------------------------------------------
# Public Procedural API Functions
# ---------------------------------------------------------------------------
async def send_report_email(
    to: Union[str, Sequence[str]],
    project_name: str,
    health_summary: Mapping[str, Any],
    dashboard_url: str,
    pdf_report: Union[bytes, str, Path],
    pdf_filename: str = DEFAULT_PDF_FILENAME,
    cc: Optional[Union[str, Sequence[str]]] = None,
    bcc: Optional[Union[str, Sequence[str]]] = None,
    reply_to: Optional[str] = None,
    subject_override: Optional[str] = None,
    config: Optional[SMTPConfig] = None,
) -> EmailSendResult:
    """
    Public asynchronous entry point for sending a project health report email.

    Compiles an HTML email body with executive health overview and direct dashboard link,
    attaches the generated PDF report, and safely transmits via aiosmtplib.

    Args:
        to: One or more recipient email addresses.
        project_name: Display name of the software project.
        health_summary: Dictionary containing health score, status badge, risks, and metrics.
        dashboard_url: Valid HTTP/HTTPS link to the web dashboard.
        pdf_report: In-memory bytes or path to the PDF report file.
        pdf_filename: Filename for the attachment (default: 'project_health_report.pdf').
        cc: Optional CC recipients.
        bcc: Optional BCC recipients.
        reply_to: Optional Reply-To address.
        subject_override: Optional custom email subject.
        config: Optional SMTPConfig instance (resolved from os.environ if omitted).

    Returns:
        EmailSendResult containing delivery confirmation and attempt metadata.

    Raises:
        EmailConfigError: If required SMTP credentials are missing from environment.
        EmailValidationError: If email addresses, URLs, headers, or attachments are invalid.
        EmailSendError: If SMTP transmission fails across all retry attempts.
    """
    service = EmailService(config=config)
    return await service.send_report(
        to=to,
        project_name=project_name,
        health_summary=health_summary,
        dashboard_url=dashboard_url,
        pdf_report=pdf_report,
        pdf_filename=pdf_filename,
        cc=cc,
        bcc=bcc,
        reply_to=reply_to,
        subject_override=subject_override,
        config=config,
    )


def send_report_email_sync(
    to: Union[str, Sequence[str]],
    project_name: str,
    health_summary: Mapping[str, Any],
    dashboard_url: str,
    pdf_report: Union[bytes, str, Path],
    pdf_filename: str = DEFAULT_PDF_FILENAME,
    cc: Optional[Union[str, Sequence[str]]] = None,
    bcc: Optional[Union[str, Sequence[str]]] = None,
    reply_to: Optional[str] = None,
    subject_override: Optional[str] = None,
    config: Optional[SMTPConfig] = None,
) -> EmailSendResult:
    """
    Public synchronous entry point for sending a project health report email.

    Compiles an HTML email body with executive health overview and direct dashboard link,
    attaches the generated PDF report, and safely transmits via standard smtplib.

    Args:
        to: One or more recipient email addresses.
        project_name: Display name of the software project.
        health_summary: Dictionary containing health score, status badge, risks, and metrics.
        dashboard_url: Valid HTTP/HTTPS link to the web dashboard.
        pdf_report: In-memory bytes or path to the PDF report file.
        pdf_filename: Filename for the attachment (default: 'project_health_report.pdf').
        cc: Optional CC recipients.
        bcc: Optional BCC recipients.
        reply_to: Optional Reply-To address.
        subject_override: Optional custom email subject.
        config: Optional SMTPConfig instance (resolved from os.environ if omitted).

    Returns:
        EmailSendResult containing delivery confirmation and attempt metadata.

    Raises:
        EmailConfigError: If required SMTP credentials are missing from environment.
        EmailValidationError: If email addresses, URLs, headers, or attachments are invalid.
        EmailSendError: If SMTP transmission fails across all retry attempts.
    """
    service = EmailService(config=config)
    return service.send_report_sync(
        to=to,
        project_name=project_name,
        health_summary=health_summary,
        dashboard_url=dashboard_url,
        pdf_report=pdf_report,
        pdf_filename=pdf_filename,
        cc=cc,
        bcc=bcc,
        reply_to=reply_to,
        subject_override=subject_override,
        config=config,
    )
