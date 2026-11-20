"""
Slack Delivery Service (TASK-SP3-08 / Issue #82)
-------------------------------------------------
Formats AI Software Project Health & Risk Analyzer status reports into Slack
Block Kit messages and delivers them to configured Slack Incoming Webhooks.

Features:
- Slack Block Kit formatting with header, prominent health score, interactive button,
  high-priority risk callouts, executive summary, and context metadata.
- Secure Slack Incoming Webhook delivery with requests.
- Strict token redaction: secret webhook tokens are NEVER logged or exposed in exceptions.
- Graceful handling of missing, null, empty, or malformed report structures.
- Robust HTTP error handling: rate limits (HTTP 429 with Retry-After), 4xx, 5xx, timeouts,
  and connection failures.
- Non-aggressive rate limiting and timeout enforcement.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

logger = logging.getLogger(__name__)

# Default timeout in seconds for Slack incoming webhook delivery
DEFAULT_SLACK_TIMEOUT: float = 10.0

# Environment variable name for default Slack webhook URL
SLACK_WEBHOOK_URL_ENV = "SLACK_WEBHOOK_URL"

# Default fallback frontend application URL
DEFAULT_APP_BASE_URL = "http://localhost:3000"

# Slack Block Kit constraints
MAX_HEADER_TEXT_LENGTH = 150
MAX_SECTION_TEXT_LENGTH = 3000
MAX_BUTTON_TEXT_LENGTH = 75
MAX_RISKS_DISPLAYED = 5
MAX_RECOMMENDATIONS_DISPLAYED = 3


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class SlackIntegrationError(Exception):
    """Base exception for all Slack integration failures."""
    pass


class SlackWebhookUrlError(SlackIntegrationError):
    """Raised when a Slack webhook URL is invalid, malformed, or missing."""
    pass


class SlackDeliveryError(SlackIntegrationError):
    """Raised when an HTTP transmission to Slack fails."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class SlackRateLimitError(SlackDeliveryError):
    """Raised when Slack responds with HTTP 429 Too Many Requests."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message, status_code=429, response_body=response_body)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SlackDeliveryResult:
    """Encapsulates the result of a Slack webhook delivery attempt."""

    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None


# ---------------------------------------------------------------------------
# Security: URL Masking
# ---------------------------------------------------------------------------

def mask_webhook_url(url: Optional[str]) -> str:
    """Return a masked representation of a Slack webhook URL safe for logging and errors.

    Slack webhook URLs contain secret tokens in their path, typically structured as:
        https://[domain]/services/<WORKSPACE_ID>/<CHANNEL_ID>/<SECRET_TOKEN>
    This helper masks all token elements to prevent accidental credential leakage in
    logs, exceptions, or audit traces.
    """
    if not url or not isinstance(url, str):
        return "<empty>"
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return "<invalid-url>"

        # Strip userinfo if present in netloc for safety
        netloc = parsed.netloc
        if "@" in netloc:
            netloc = netloc.split("@")[-1]

        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "services":
            masked_path = f"/services/{parts[1][:3]}.../{parts[2][:3]}.../<REDACTED>"
        elif parts:
            masked_path = f"/{parts[0]}/<REDACTED>"
        else:
            masked_path = "/<REDACTED>"
        return f"{parsed.scheme}://{netloc}{masked_path}"
    except Exception:
        return "<malformed-url>"


# ---------------------------------------------------------------------------
# Webhook Validation
# ---------------------------------------------------------------------------

def validate_webhook_url(url: Optional[str]) -> str:
    """Validate that the provided webhook URL is a valid, secure HTTPS URL.

    Args:
        url: The webhook URL string to validate.

    Returns:
        The cleaned, validated URL string.

    Raises:
        SlackWebhookUrlError: If URL is missing, empty, not a string, not HTTPS,
                              contains embedded credentials, invalid host, or malformed.
    """
    if url is None:
        raise SlackWebhookUrlError("Slack webhook URL must not be None.")
    if not isinstance(url, str):
        raise SlackWebhookUrlError(
            f"Slack webhook URL must be a string, got {type(url).__name__}."
        )

    cleaned = url.strip()
    if not cleaned:
        raise SlackWebhookUrlError("Slack webhook URL must not be empty.")

    try:
        parsed = urllib.parse.urlsplit(cleaned)
    except Exception as exc:
        raise SlackWebhookUrlError("Malformed Slack webhook URL.") from exc

    if not parsed.scheme:
        raise SlackWebhookUrlError("Malformed Slack webhook URL: missing scheme.")

    if parsed.scheme.lower() != "https":
        raise SlackWebhookUrlError(
            f"Unsupported scheme '{parsed.scheme}'; Slack webhook URLs must use HTTPS."
        )

    if not parsed.netloc:
        raise SlackWebhookUrlError("Malformed Slack webhook URL: missing hostname.")

    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise SlackWebhookUrlError("Slack webhook URL must not contain embedded user credentials.")

    # Check for invalid host characters
    if any(c in parsed.netloc for c in (" ", "\t", "\r", "\n")):
        raise SlackWebhookUrlError("Malformed Slack webhook URL: invalid hostname characters.")

    hostname = (parsed.hostname or "").lower()
    allowed_hosts = ("hooks.slack.com", "localhost", "127.0.0.1")
    if hostname not in allowed_hosts and not hostname.endswith(".slack.com"):
        raise SlackWebhookUrlError(
            f"Invalid Slack webhook host '{hostname}'. Host must be 'hooks.slack.com' or end with '.slack.com'."
        )

    if parsed.query:
        raise SlackWebhookUrlError("Slack webhook URL must not contain query parameters.")

    if parsed.fragment:
        raise SlackWebhookUrlError("Slack webhook URL must not contain URL fragments.")

    # Path must be present and not just root
    if not parsed.path or parsed.path.strip("/") == "":
        raise SlackWebhookUrlError("Malformed Slack webhook URL: missing webhook path.")

    return cleaned


# ---------------------------------------------------------------------------
# Report Data Extraction & Normalization
# ---------------------------------------------------------------------------

def _extract_health_score(
    report_data: Dict[str, Any],
) -> Tuple[Optional[int], str, Optional[str], Optional[float]]:
    """Extract (score, status, confidence, coverage_ratio) from various report formats."""
    if not isinstance(report_data, dict):
        return None, "Unknown", None, None

    # Try top-level keys (e.g. GeneratedReportResponse)
    score = report_data.get("health_score")
    status = report_data.get("health_status")
    confidence = None
    coverage_ratio = None

    # Try project_health dictionary (pipeline_v2 or metricsSnapshot)
    health_obj = report_data.get("project_health")
    if not isinstance(health_obj, dict):
        snapshot = report_data.get("metricsSnapshot")
        if isinstance(snapshot, dict):
            health_obj = snapshot.get("project_health")
        elif isinstance(report_data.get("report"), dict):
            health_obj = report_data["report"].get("project_health")

    if isinstance(health_obj, dict):
        if score is None:
            score = health_obj.get("score")
        if status is None:
            status = health_obj.get("status")
        confidence = health_obj.get("confidence")
        coverage_ratio = health_obj.get("coverage_ratio")

    # Normalize score to int if numeric
    if score is not None:
        try:
            score = int(round(float(score)))
        except (ValueError, TypeError):
            score = None

    # Normalize status string
    status_str = str(status or "Unknown").strip().title()
    if status_str.lower() in ("at_risk", "at risk"):
        status_str = "At Risk"
    elif status_str.lower() in ("needs_attention", "needs attention"):
        status_str = "Needs Attention"

    return score, status_str, confidence, coverage_ratio


def _extract_project_info(
    report_data: Dict[str, Any],
    explicit_project_name: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Extract display project name and project ID from input or report."""
    if explicit_project_name and str(explicit_project_name).strip():
        return str(explicit_project_name).strip(), str(report_data.get("project_id") or report_data.get("projectId") or "") or None

    if not isinstance(report_data, dict):
        return "Software Project", None

    # Look for candidate name fields
    candidates = [
        report_data.get("project_name"),
        report_data.get("projectName"),
        report_data.get("name"),
    ]
    for c in candidates:
        if c and str(c).strip():
            return str(c).strip(), str(report_data.get("project_id") or report_data.get("projectId") or "") or None

    project_id = str(report_data.get("project_id") or report_data.get("projectId") or "").strip() or None
    if project_id:
        return f"Project ({project_id[:8]})", project_id

    return "Software Project", None


def _extract_risks(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and normalize risk factors from report payload."""
    if not isinstance(report_data, dict):
        return []

    raw_risks = report_data.get("risks")
    if not isinstance(raw_risks, list):
        health = report_data.get("project_health")
        if isinstance(health, dict):
            raw_risks = health.get("risk_factors")
        elif isinstance(report_data.get("metricsSnapshot"), dict):
            raw_risks = report_data["metricsSnapshot"].get("risks") or (
                report_data["metricsSnapshot"].get("project_health", {}).get("risk_factors")
            )
        elif isinstance(report_data.get("report"), dict):
            raw_risks = report_data["report"].get("project_health", {}).get("risk_factors")

    if not isinstance(raw_risks, list):
        return []

    normalized_risks: List[Dict[str, Any]] = []
    for item in raw_risks:
        if isinstance(item, dict):
            normalized_risks.append({
                "risk_id": str(item.get("risk_id") or item.get("id") or "unspecified_risk"),
                "severity": str(item.get("severity") or "medium").strip().lower(),
                "evidence": str(item.get("evidence") or item.get("description") or "").strip(),
                "recommendation": str(item.get("recommendation") or "").strip(),
            })
        elif isinstance(item, str) and item.strip():
            normalized_risks.append({
                "risk_id": item.strip(),
                "severity": "medium",
                "evidence": item.strip(),
                "recommendation": "",
            })
    return normalized_risks


def _extract_summary(report_data: Dict[str, Any]) -> str:
    """Extract executive summary from report payload."""
    if not isinstance(report_data, dict):
        return ""

    candidates = [
        report_data.get("executive_summary"),
        report_data.get("summary"),
    ]
    if isinstance(report_data.get("report"), dict):
        candidates.append(report_data["report"].get("executive_summary"))

    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()

    return ""


def _extract_recommendations(report_data: Dict[str, Any]) -> List[str]:
    """Extract list of recommendations from report payload."""
    if not isinstance(report_data, dict):
        return []

    recs = report_data.get("recommendations")
    if not isinstance(recs, list) and isinstance(report_data.get("report"), dict):
        recs = report_data["report"].get("recommendations")

    if not isinstance(recs, list):
        return []

    clean: List[str] = []
    for r in recs:
        if isinstance(r, str) and r.strip():
            clean.append(r.strip())
        elif isinstance(r, dict) and r.get("recommendation"):
            clean.append(str(r["recommendation"]).strip())
    return clean


def _resolve_report_url(
    report_data: Dict[str, Any],
    project_id: Optional[str] = None,
    explicit_url: Optional[str] = None,
) -> str:
    """Resolve an action link URL for the report button in Slack."""
    if explicit_url and isinstance(explicit_url, str) and explicit_url.strip():
        cleaned = explicit_url.strip()
        if cleaned.startswith(("http://", "https://")):
            return cleaned

    # Check for report_url or url in payload
    if isinstance(report_data, dict):
        for key in ("report_url", "url"):
            val = report_data.get(key)
            if isinstance(val, str) and val.strip().startswith(("http://", "https://")):
                return val.strip()

    # Determine base URL from environment without inventing private details
    base_url = (
        os.getenv("APP_URL")
        or os.getenv("FRONTEND_URL")
        or os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")[0].strip()
        or DEFAULT_APP_BASE_URL
    ).rstrip("/")

    # Ensure base_url has a valid protocol
    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"

    # Build project/report path if identifiers exist
    pid = project_id or (report_data.get("project_id") if isinstance(report_data, dict) else None)
    rid = report_data.get("report_id") or report_data.get("_id") if isinstance(report_data, dict) else None

    if pid and rid:
        return f"{base_url}/projects/{pid}/reports/{rid}"
    if pid:
        return f"{base_url}/projects/{pid}"
    return base_url


# ---------------------------------------------------------------------------
# Slack Block Kit Formatter
# ---------------------------------------------------------------------------

def format_slack_report_blocks(
    report_data: Dict[str, Any],
    project_name: Optional[str] = None,
    report_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert status report data into valid Slack Block Kit blocks.

    Args:
        report_data: Status report dictionary.
        project_name: Optional explicit project name.
        report_url: Optional explicit report action URL.

    Returns:
        A list of Slack Block Kit block dictionaries.
    """
    if not isinstance(report_data, dict):
        report_data = {}

    display_name, project_id = _extract_project_info(report_data, project_name)
    score, status_str, confidence, coverage_ratio = _extract_health_score(report_data)
    risks = _extract_risks(report_data)
    summary_text = _extract_summary(report_data)
    recommendations = _extract_recommendations(report_data)
    effective_url = _resolve_report_url(report_data, project_id, report_url)

    blocks: List[Dict[str, Any]] = []

    # 1. Header Block
    header_title = f"Project Health Report: {display_name}"
    if len(header_title) > MAX_HEADER_TEXT_LENGTH:
        header_title = header_title[:MAX_HEADER_TEXT_LENGTH - 3] + "..."
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header_title,
            "emoji": True,
        },
    })

    # 2. Prominent Health Score & Button Section
    if score is not None:
        score_display = f"{score}/100"
        if score >= 75:
            status_badge = "🟢 *HEALTHY*"
            button_style = "primary"
        elif score >= 50:
            status_badge = "🟡 *NEEDS ATTENTION*"
            button_style = None  # default gray
        else:
            status_badge = "🔴 *AT RISK*"
            button_style = "danger"
    else:
        score_display = "N/A"
        status_badge = "⚪ *NOT ASSESSED*"
        button_style = None

    confidence_str = f" | *Confidence:* {str(confidence).title()}" if confidence else ""
    coverage_str = f" | *Coverage:* {round(float(coverage_ratio) * 100)}%" if coverage_ratio is not None else ""

    score_section_text = (
        f"*Project:* {display_name}\n"
        f"*Health Score:* *`{score_display}`* — {status_badge}"
        f"{confidence_str}{coverage_str}"
    )

    score_block: Dict[str, Any] = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": score_section_text[:MAX_SECTION_TEXT_LENGTH],
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "📊 View Full Report",
                "emoji": True,
            },
            "url": effective_url,
            "action_id": "view_full_report_action",
        },
    }
    if button_style:
        score_block["accessory"]["style"] = button_style

    blocks.append(score_block)

    # 3. Executive Summary
    if summary_text:
        # Sanitize text length
        truncated_summary = summary_text.strip()
        if len(truncated_summary) > 800:
            truncated_summary = truncated_summary[:797] + "..."
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Executive Summary:*\n{truncated_summary}",
            },
        })

    # 4. Divider
    blocks.append({"type": "divider"})

    # 5. Risk Factors Callouts
    high_risks = [r for r in risks if r.get("severity") == "high"]
    other_risks = [r for r in risks if r.get("severity") != "high"]

    if high_risks:
        high_risk_lines = []
        for r in high_risks[:3]:
            name = r.get("risk_id", "high_risk").replace("_", " ").title()
            ev = r.get("evidence", "")
            if ev:
                ev_snippet = ev[:150] + ("..." if len(ev) > 150 else "")
                high_risk_lines.append(f"• 🚨 *{name}* (HIGH): {ev_snippet}")
            else:
                high_risk_lines.append(f"• 🚨 *{name}* (HIGH)")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🚨 High-Priority Risks Detected:*\n" + "\n".join(high_risk_lines),
            },
        })

    if other_risks:
        other_risk_lines = []
        for r in other_risks[:3]:
            name = r.get("risk_id", "risk").replace("_", " ").title()
            sev = r.get("severity", "medium").upper()
            ev = r.get("evidence", "")
            if ev:
                ev_snippet = ev[:120] + ("..." if len(ev) > 120 else "")
                other_risk_lines.append(f"• ⚠️ *{name}* ({sev}): {ev_snippet}")
            else:
                other_risk_lines.append(f"• ⚠️ *{name}* ({sev})")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*⚠️ Other Active Risk Factors:*\n" + "\n".join(other_risk_lines),
            },
        })

    if not risks:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "✅ *Risk Assessment:* No active project risks detected.",
            },
        })

    # 6. Key Recommendations (if present)
    if recommendations:
        rec_lines = [f"• {rec[:140]}" for rec in recommendations[:MAX_RECOMMENDATIONS_DISPLAYED]]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*💡 Recommended Actions:*\n" + "\n".join(rec_lines),
            },
        })

    # 7. Context Footer
    generated_at = report_data.get("generated_at") or report_data.get("generatedAt") or "Recently"
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Generated: {generated_at} | AI Software Project Health Analyzer",
            }
        ],
    })

    return blocks


def build_slack_payload(
    report_data: Dict[str, Any],
    project_name: Optional[str] = None,
    report_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the complete JSON payload ready for a Slack Incoming Webhook.

    Args:
        report_data: Status report data dictionary.
        project_name: Optional explicit project name.
        report_url: Optional explicit report link URL.

    Returns:
        Dictionary containing 'text' (fallback notification) and 'blocks'.
    """
    blocks = format_slack_report_blocks(report_data, project_name=project_name, report_url=report_url)
    display_name, _ = _extract_project_info(report_data, project_name)
    score, status_str, _, _ = _extract_health_score(report_data)

    score_text = f"Score: {score}/100 ({status_str})" if score is not None else f"Status: {status_str}"
    fallback_text = f"Project Health Report: {display_name} — {score_text}"

    return {
        "text": fallback_text,
        "blocks": blocks,
    }


# ---------------------------------------------------------------------------
# Slack Incoming Webhook Delivery
# ---------------------------------------------------------------------------

def post_to_slack_webhook(
    webhook_url: str,
    payload: Dict[str, Any],
    timeout: float = DEFAULT_SLACK_TIMEOUT,
    raise_on_error: bool = False,
    session: Optional[requests.Session] = None,
) -> SlackDeliveryResult:
    """Send a formatted JSON payload to a Slack Incoming Webhook.

    Args:
        webhook_url: Target Slack Incoming Webhook HTTPS URL.
        payload: JSON dictionary containing blocks and fallback text.
        timeout: HTTP request timeout in seconds.
        raise_on_error: If True, raises custom exceptions on failure instead of
                        returning SlackDeliveryResult.
        session: Optional requests.Session instance for dependency injection.

    Returns:
        SlackDeliveryResult with delivery outcome, status code, and retry information.

    Raises:
        SlackWebhookUrlError: If webhook URL fails validation (when raise_on_error=True).
        SlackRateLimitError: If Slack returns HTTP 429 (when raise_on_error=True).
        SlackDeliveryError: If Slack returns an error response or network fails
                            (when raise_on_error=True).
    """
    # 1. URL validation
    try:
        validated_url = validate_webhook_url(webhook_url)
    except SlackWebhookUrlError as exc:
        logger.error("Slack webhook delivery rejected: %s", exc)
        if raise_on_error:
            raise
        return SlackDeliveryResult(success=False, error=str(exc))

    masked_url = mask_webhook_url(validated_url)

    # 2. Payload validation
    if not isinstance(payload, dict) or not payload:
        err_msg = "Slack payload must be a non-empty JSON dictionary."
        logger.error("Slack webhook delivery error: %s (Target: %s)", err_msg, masked_url)
        if raise_on_error:
            raise SlackDeliveryError(err_msg)
        return SlackDeliveryResult(success=False, error=err_msg)

    # 3. HTTP Delivery
    http = session or requests
    try:
        logger.info("Posting report notification to Slack webhook %s", masked_url)
        response = http.post(
            validated_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )

        status_code = response.status_code
        response_text = response.text or ""

        # A. HTTP 200 Success
        if status_code == 200 and response_text.strip().lower() == "ok":
            logger.info("Slack notification delivered successfully to %s", masked_url)
            return SlackDeliveryResult(
                success=True,
                status_code=200,
                response_body=response_text,
            )

        # B. HTTP 429 Rate Limiting
        if status_code == 429:
            retry_after_header = response.headers.get("Retry-After")
            retry_after: Optional[int] = None
            if retry_after_header:
                try:
                    retry_after = max(0, int(float(retry_after_header)))
                except (ValueError, TypeError):
                    retry_after = None

            retry_info = f"{retry_after}s" if retry_after is not None else "unspecified"
            logger.warning(
                "Slack webhook rate-limited (HTTP 429). Retry-After: %s. Webhook: %s",
                retry_info,
                masked_url,
            )
            err_msg = f"Slack webhook rate limit exceeded (HTTP 429). Retry after {retry_info}."
            if raise_on_error:
                raise SlackRateLimitError(
                    err_msg,
                    retry_after=retry_after,
                    response_body=response_text,
                )
            return SlackDeliveryResult(
                success=False,
                status_code=429,
                response_body=response_text,
                retry_after=retry_after,
                error=err_msg,
            )

        # C. Other Unsuccessful HTTP Responses (400, 403, 404, 500, etc.)
        err_msg = (
            f"Slack webhook HTTP {status_code} error: {response_text[:200]}"
            f" (Webhook: {masked_url})"
        )
        logger.error(
            "Slack webhook delivery failed with HTTP %d for %s: %s",
            status_code,
            masked_url,
            response_text[:200],
        )
        if raise_on_error:
            raise SlackDeliveryError(
                err_msg,
                status_code=status_code,
                response_body=response_text,
            )
        return SlackDeliveryResult(
            success=False,
            status_code=status_code,
            response_body=response_text,
            error=err_msg,
        )

    except (SlackWebhookUrlError, SlackDeliveryError):
        # Already handled above if raised
        raise

    except requests.exceptions.Timeout as exc:
        err_msg = f"Slack webhook request timed out after {timeout} seconds (Webhook: {masked_url})."
        logger.error("Slack delivery timeout: %s", err_msg)
        if raise_on_error:
            raise SlackDeliveryError(err_msg) from exc
        return SlackDeliveryResult(success=False, error=err_msg)

    except requests.exceptions.ConnectionError as exc:
        err_msg = f"Failed to establish connection to Slack webhook (Webhook: {masked_url})."
        logger.error("Slack connection failure: %s", err_msg)
        if raise_on_error:
            raise SlackDeliveryError(err_msg) from exc
        return SlackDeliveryResult(success=False, error=err_msg)

    except requests.exceptions.RequestException as exc:
        err_msg = f"Network exception during Slack webhook delivery (Webhook: {masked_url})."
        logger.error("Slack network exception: %s (%s)", err_msg, exc)
        if raise_on_error:
            raise SlackDeliveryError(err_msg) from exc
        return SlackDeliveryResult(success=False, error=err_msg)

    except Exception as exc:
        err_msg = f"Unexpected error during Slack webhook delivery (Webhook: {masked_url})."
        logger.error("Unexpected Slack delivery error: %s (%s)", err_msg, exc, exc_info=True)
        if raise_on_error:
            raise SlackDeliveryError(err_msg) from exc
        return SlackDeliveryResult(success=False, error=err_msg)


def send_slack_report(
    report_data: Dict[str, Any],
    webhook_url: Optional[str] = None,
    project_name: Optional[str] = None,
    report_url: Optional[str] = None,
    timeout: float = DEFAULT_SLACK_TIMEOUT,
    raise_on_error: bool = False,
    session: Optional[requests.Session] = None,
) -> SlackDeliveryResult:
    """Format and deliver a project health status report to a Slack Incoming Webhook.

    Args:
        report_data: Status report data dictionary.
        webhook_url: Slack webhook URL. If omitted, falls back to the SLACK_WEBHOOK_URL
                     environment variable.
        project_name: Optional explicit project name.
        report_url: Optional explicit report action link URL.
        timeout: Network timeout in seconds.
        raise_on_error: If True, raises exceptions on delivery or validation errors.
        session: Optional requests.Session for testing or connection pooling.

    Returns:
        SlackDeliveryResult detailing the delivery outcome.
    """
    target_url = webhook_url or os.getenv(SLACK_WEBHOOK_URL_ENV)

    if not target_url:
        err_msg = (
            f"No Slack webhook URL provided and ${SLACK_WEBHOOK_URL_ENV} "
            "environment variable is not set."
        )
        logger.error("Slack report dispatch aborted: %s", err_msg)
        if raise_on_error:
            raise SlackWebhookUrlError(err_msg)
        return SlackDeliveryResult(success=False, error=err_msg)

    payload = build_slack_payload(report_data, project_name=project_name, report_url=report_url)

    return post_to_slack_webhook(
        webhook_url=target_url,
        payload=payload,
        timeout=timeout,
        raise_on_error=raise_on_error,
        session=session,
    )
