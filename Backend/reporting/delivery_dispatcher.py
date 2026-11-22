"""
Delivery Dispatcher for Project Health & Risk Reports.
------------------------------------------------------
Dispatches generated reports to configured destinations:
- Dashboard (internal persistence and published view)
- Email (SMTP notification with HTML/plain-text summary)
- Slack (Block Kit cards posted to incoming webhook)

Records all delivery attempt outcomes, timestamps, and error codes in MongoDB.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bson import ObjectId

from Backend.database import db, reports_collection
from Backend.persistence import to_object_id

logger = logging.getLogger(__name__)

# Delivery attempts collection
delivery_attempts_collection = db["delivery_attempts"]


# ---------------------------------------------------------------------------
# Enums and Error Codes
# ---------------------------------------------------------------------------

class DeliveryDestination(str, Enum):
    """Supported report delivery destinations."""
    DASHBOARD = "dashboard"
    EMAIL = "email"
    SLACK = "slack"


class DeliveryStatus(str, Enum):
    """Status outcomes for a delivery attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class DeliveryErrorCode(str, Enum):
    """Standardized error codes for reporting and auditing delivery failures."""
    NO_RECIPIENTS = "ERR_NO_RECIPIENTS"
    SMTP_NOT_CONFIGURED = "ERR_SMTP_NOT_CONFIGURED"
    SMTP_FAILURE = "ERR_SMTP_FAILURE"
    NO_SLACK_WEBHOOK = "ERR_NO_SLACK_WEBHOOK"
    SLACK_HTTP_ERROR = "ERR_SLACK_HTTP_ERROR"
    SLACK_NETWORK_ERROR = "ERR_SLACK_NETWORK_ERROR"
    DASHBOARD_PERSIST_FAILED = "ERR_DASHBOARD_PERSIST_FAILED"
    UNSUPPORTED_DESTINATION = "ERR_UNSUPPORTED_DESTINATION"
    REPORT_NOT_FOUND = "ERR_REPORT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Persistence Helpers
# ---------------------------------------------------------------------------

def record_delivery_attempt(attempt_data: Dict[str, Any]) -> str:
    """
    Persist a delivery attempt record in MongoDB and update the associated report.
    Returns the string ID of the inserted delivery attempt.
    """
    clean_report_id = attempt_data.get("report_id")
    clean_project_id = attempt_data.get("project_id")

    record = {
        "reportId": to_object_id(clean_report_id) if clean_report_id else None,
        "projectId": to_object_id(clean_project_id) if clean_project_id else None,
        "destination": str(attempt_data.get("destination", "")).lower(),
        "status": str(attempt_data.get("status", DeliveryStatus.PENDING.value)),
        "attemptedAt": attempt_data.get("attempted_at") or datetime.now(timezone.utc),
        "errorCode": attempt_data.get("error_code"),
        "errorMessage": attempt_data.get("error_message"),
        "metadata": attempt_data.get("metadata") or {},
    }

    try:
        result = delivery_attempts_collection.insert_one(record)
        attempt_id = str(result.inserted_id)

        # Mirror attempt summary on the report document if present
        if clean_report_id:
            try:
                reports_collection.update_one(
                    {"_id": to_object_id(clean_report_id)},
                    {
                        "$push": {
                            "deliveryAttempts": {
                                "attemptId": attempt_id,
                                "destination": record["destination"],
                                "status": record["status"],
                                "attemptedAt": record["attemptedAt"],
                                "errorCode": record["errorCode"],
                                "errorMessage": record["errorMessage"],
                            }
                        },
                        "$set": {
                            f"deliveryStatus.{record['destination']}": record["status"],
                            "lastDeliveredAt": record["attemptedAt"],
                        },
                    },
                )
            except Exception as e:
                logger.warning("Could not update report %s with delivery attempt: %s", clean_report_id, e)

        return attempt_id
    except Exception as exc:
        logger.error("Failed to persist delivery attempt: %s", exc)
        return ""


def get_delivery_attempts(
    report_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve delivery attempt history by report ID or project ID."""
    query: Dict[str, Any] = {}
    if report_id:
        query["reportId"] = to_object_id(report_id)
    if project_id:
        query["projectId"] = to_object_id(project_id)

    cursor = delivery_attempts_collection.find(query).sort("attemptedAt", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    for doc in cursor:
        doc["id"] = str(doc.get("_id"))
        doc["reportId"] = str(doc.get("reportId", ""))
        doc["projectId"] = str(doc.get("projectId", ""))
        if isinstance(doc.get("attemptedAt"), datetime):
            doc["attemptedAt"] = doc["attemptedAt"].isoformat()
        out.append(doc)
    return out


# ---------------------------------------------------------------------------
# Message Builders
# ---------------------------------------------------------------------------

def build_report_email_content(report: Dict[str, Any]) -> tuple[str, str, str]:
    """
    Format report into (subject, plain_text_body, html_body).
    """
    project_name = report.get("projectName") or report.get("project_name") or "Software Project"
    health_status = report.get("status") or report.get("health_status") or "Unknown"
    health_score = report.get("healthScore") or report.get("health_score")
    score_display = f"{health_score:.1f}/100" if isinstance(health_score, (int, float)) else "N/A"
    summary_text = (
        report.get("summaryStatement")
        or report.get("summary_statement")
        or report.get("executive_summary")
        or "No summary provided."
    )
    active_flags = report.get("activeFlags") or report.get("active_flags") or []
    flags_count = len(active_flags)

    subject = f"[कVaच] Health Report: {project_name} - {health_status} ({score_display})"

    # Plain text body
    lines = [
        f"कVaच Project Health Report",
        f"==============================",
        f"Project:      {project_name}",
        f"Health:       {health_status} (Score: {score_display})",
        f"Generated At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Executive Summary:",
        f"{summary_text}",
        "",
        f"Active Risk Flags: {flags_count}",
    ]
    for flag in active_flags[:5]:
        flag_type = flag.get("type", "flag")
        severity = flag.get("severity", "info").upper()
        msg = flag.get("message", "")
        lines.append(f"  • [{severity}] ({flag_type}): {msg}")

    lines.extend([
        "",
        "View the full interactive telemetry breakdown in your कVaच Dashboard.",
        "---",
        "Automated notification sent by कVaच Project Health Analyzer.",
    ])
    plain_body = "\n".join(lines)

    # HTML body
    flag_html = ""
    for flag in active_flags[:5]:
        severity = str(flag.get("severity", "info")).lower()
        badge_color = "#ef4444" if severity == "high" else ("#f59e0b" if severity == "medium" else "#3b82f6")
        flag_html += f"""
        <li style="margin-bottom: 8px;">
          <span style="background-color: {badge_color}; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase;">
            {flag.get('severity', 'info')}
          </span>
          <strong style="margin-left: 6px; color: #1e293b;">{flag.get('type', 'risk')}:</strong>
          <span style="color: #475569;">{flag.get('message', '')}</span>
        </li>
        """

    status_color = "#10b981" if health_status.lower() == "good" else ("#f59e0b" if health_status.lower() == "caution" else "#ef4444")

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; padding: 24px; color: #0f172a;">
      <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
        <div style="background-color: #0c1022; padding: 20px 24px; color: #ffffff;">
          <h2 style="margin: 0; font-size: 20px; font-weight: 700;">कVaच Health Report</h2>
          <p style="margin: 4px 0 0; font-size: 13px; color: #94a3b8;">Automated Recurring Project Health & Risk Telemetry</p>
        </div>
        <div style="padding: 24px;">
          <h3 style="margin-top: 0; font-size: 18px; color: #0f172a;">{project_name}</h3>
          <div style="display: inline-block; padding: 6px 14px; border-radius: 20px; background-color: {status_color}15; color: {status_color}; font-weight: bold; font-size: 14px; margin-bottom: 16px;">
            {health_status} &bull; Score: {score_display}
          </div>
          <div style="background-color: #f1f5f9; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #334155;">{summary_text}</p>
          </div>
          <h4 style="margin: 0 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b;">
            Active Risk Flags ({flags_count})
          </h4>
          <ul style="padding-left: 20px; margin: 0 0 24px; font-size: 13px;">
            {flag_html or '<li style="color: #64748b;">No active delivery flags detected. Project velocity is healthy.</li>'}
          </ul>
        </div>
        <div style="background-color: #f8fafc; padding: 14px 24px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
          Sent by कVaच Automated Report Dispatcher
        </div>
      </div>
    </body>
    </html>
    """

    return subject, plain_body, html_body


def build_slack_blocks(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format report into Slack Block Kit card payload.
    """
    project_name = report.get("projectName") or report.get("project_name") or "Software Project"
    health_status = report.get("status") or report.get("health_status") or "Unknown"
    health_score = report.get("healthScore") or report.get("health_score")
    score_display = f"{health_score:.1f}/100" if isinstance(health_score, (int, float)) else "N/A"
    summary_text = (
        report.get("summaryStatement")
        or report.get("summary_statement")
        or report.get("executive_summary")
        or "No summary statement available."
    )
    active_flags = report.get("activeFlags") or report.get("active_flags") or []

    status_emoji = ":white_check_mark:" if health_status.lower() == "good" else (":warning:" if health_status.lower() == "caution" else ":rotating_light:")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":bar_chart: कVaच Report: {project_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Health Status:*\n{status_emoji} *{health_status}*",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Health Score:*\n`{score_display}`",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Executive Summary:*\n>{summary_text}",
            },
        },
    ]

    if active_flags:
        flag_lines = []
        for f in active_flags[:4]:
            sev = str(f.get("severity", "info")).upper()
            flag_lines.append(f"• `[{sev}]` *{f.get('type', 'risk')}*: {f.get('message', '')}")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Active Risk Flags ({len(active_flags)}):*\n" + "\n".join(flag_lines),
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | कVaच Automated Dispatcher",
            }
        ],
    })

    return {"text": f"Project Health Report: {project_name} - {health_status} ({score_display})", "blocks": blocks}


# ---------------------------------------------------------------------------
# Dispatcher Engine
# ---------------------------------------------------------------------------

class DeliveryDispatcher:
    """
    Orchestrates report delivery to Dashboard, Email, and Slack.
    Records delivery outcomes, timestamps, and error codes in database.
    """

    def __init__(
        self,
        email_sender: Optional[Callable[[List[str], str, str, str], bool]] = None,
        http_poster: Optional[Callable[[str, Dict[str, Any]], tuple[int, str]]] = None,
    ):
        """
        Optional custom adapters can be injected for deterministic testing.
        """
        self._custom_email_sender = email_sender
        self._custom_http_poster = http_poster

    def dispatch(
        self,
        report: Dict[str, Any],
        destinations: List[str],
        project_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Dispatch a single report to all configured destinations.
        Returns a dictionary mapping destination to its outcome summary.
        """
        project_config = project_config or {}
        report_id = str(report.get("_id") or report.get("id") or "")
        project_id = str(
            report.get("projectId")
            or report.get("project_id")
            or project_config.get("project_id")
            or ""
        )

        results: Dict[str, Dict[str, Any]] = {}

        for raw_dest in destinations:
            dest = raw_dest.strip().lower()
            if dest == DeliveryDestination.DASHBOARD.value:
                outcome = self._dispatch_dashboard(report, report_id, project_id, project_config)
            elif dest == DeliveryDestination.EMAIL.value:
                outcome = self._dispatch_email(report, report_id, project_id, project_config)
            elif dest == DeliveryDestination.SLACK.value:
                outcome = self._dispatch_slack(report, report_id, project_id, project_config)
            else:
                outcome = self._record_failure(
                    report_id=report_id,
                    project_id=project_id,
                    destination=dest,
                    error_code=DeliveryErrorCode.UNSUPPORTED_DESTINATION.value,
                    error_message=f"Unsupported destination: '{raw_dest}'. Supported: dashboard, email, slack.",
                )
            results[dest] = outcome

        return results

    # -----------------------------------------------------------------------
    # Destination Handlers
    # -----------------------------------------------------------------------

    def _dispatch_dashboard(
        self,
        report: Dict[str, Any],
        report_id: str,
        project_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Publish report to dashboard collection."""
        try:
            if report_id:
                reports_collection.update_one(
                    {"_id": to_object_id(report_id)},
                    {
                        "$set": {
                            "dashboardPublished": True,
                            "publishedAt": datetime.now(timezone.utc),
                        }
                    },
                )
            attempt_id = record_delivery_attempt({
                "report_id": report_id,
                "project_id": project_id,
                "destination": DeliveryDestination.DASHBOARD.value,
                "status": DeliveryStatus.SUCCESS.value,
                "error_code": None,
                "error_message": None,
                "metadata": {"dashboardPublished": True},
            })
            return {
                "attempt_id": attempt_id,
                "status": DeliveryStatus.SUCCESS.value,
                "destination": DeliveryDestination.DASHBOARD.value,
                "error_code": None,
            }
        except Exception as e:
            return self._record_failure(
                report_id=report_id,
                project_id=project_id,
                destination=DeliveryDestination.DASHBOARD.value,
                error_code=DeliveryErrorCode.DASHBOARD_PERSIST_FAILED.value,
                error_message=str(e),
            )

    def _dispatch_email(
        self,
        report: Dict[str, Any],
        report_id: str,
        project_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deliver report via email to configured recipients."""
        recipients = (
            config.get("email_recipients")
            or config.get("recipients")
            or report.get("email_recipients")
            or []
        )
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",") if r.strip()]

        if not recipients:
            attempt_id = record_delivery_attempt({
                "report_id": report_id,
                "project_id": project_id,
                "destination": DeliveryDestination.EMAIL.value,
                "status": DeliveryStatus.SKIPPED.value,
                "error_code": DeliveryErrorCode.NO_RECIPIENTS.value,
                "error_message": "No email recipients configured for project report delivery.",
                "metadata": {"recipients": []},
            })
            return {
                "attempt_id": attempt_id,
                "status": DeliveryStatus.SKIPPED.value,
                "destination": DeliveryDestination.EMAIL.value,
                "error_code": DeliveryErrorCode.NO_RECIPIENTS.value,
            }

        subject, plain_body, html_body = build_report_email_content(report)

        # Custom sender adapter if provided (testing or service integration)
        if self._custom_email_sender:
            try:
                success = self._custom_email_sender(recipients, subject, plain_body, html_body)
                if success:
                    attempt_id = record_delivery_attempt({
                        "report_id": report_id,
                        "project_id": project_id,
                        "destination": DeliveryDestination.EMAIL.value,
                        "status": DeliveryStatus.SUCCESS.value,
                        "error_code": None,
                        "error_message": None,
                        "metadata": {"recipients": recipients, "count": len(recipients)},
                    })
                    return {
                        "attempt_id": attempt_id,
                        "status": DeliveryStatus.SUCCESS.value,
                        "destination": DeliveryDestination.EMAIL.value,
                        "error_code": None,
                    }
                else:
                    return self._record_failure(
                        report_id=report_id,
                        project_id=project_id,
                        destination=DeliveryDestination.EMAIL.value,
                        error_code=DeliveryErrorCode.SMTP_FAILURE.value,
                        error_message="Custom email sender returned false.",
                        metadata={"recipients": recipients},
                    )
            except Exception as exc:
                return self._record_failure(
                    report_id=report_id,
                    project_id=project_id,
                    destination=DeliveryDestination.EMAIL.value,
                    error_code=DeliveryErrorCode.SMTP_FAILURE.value,
                    error_message=str(exc),
                    metadata={"recipients": recipients},
                )

        # Standard SMTP sending
        smtp_host = os.getenv("SMTP_HOST") or config.get("smtp_host")
        smtp_port = int(os.getenv("SMTP_PORT") or config.get("smtp_port") or 587)
        smtp_user = os.getenv("SMTP_USER") or config.get("smtp_user")
        smtp_pass = os.getenv("SMTP_PASSWORD") or config.get("smtp_password")
        smtp_from = os.getenv("SMTP_FROM") or config.get("smtp_from") or "aegis-ai@noreply.internal"

        if not smtp_host:
            attempt_id = record_delivery_attempt({
                "report_id": report_id,
                "project_id": project_id,
                "destination": DeliveryDestination.EMAIL.value,
                "status": DeliveryStatus.SKIPPED.value,
                "error_code": DeliveryErrorCode.SMTP_NOT_CONFIGURED.value,
                "error_message": "SMTP host not configured (missing SMTP_HOST environment variable).",
                "metadata": {"recipients": recipients},
            })
            return {
                "attempt_id": attempt_id,
                "status": DeliveryStatus.SKIPPED.value,
                "destination": DeliveryDestination.EMAIL.value,
                "error_code": DeliveryErrorCode.SMTP_NOT_CONFIGURED.value,
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                if os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1"):
                    server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, recipients, msg.as_string())

            attempt_id = record_delivery_attempt({
                "report_id": report_id,
                "project_id": project_id,
                "destination": DeliveryDestination.EMAIL.value,
                "status": DeliveryStatus.SUCCESS.value,
                "error_code": None,
                "error_message": None,
                "metadata": {"recipients": recipients, "count": len(recipients), "host": smtp_host},
            })
            return {
                "attempt_id": attempt_id,
                "status": DeliveryStatus.SUCCESS.value,
                "destination": DeliveryDestination.EMAIL.value,
                "error_code": None,
            }
        except Exception as exc:
            return self._record_failure(
                report_id=report_id,
                project_id=project_id,
                destination=DeliveryDestination.EMAIL.value,
                error_code=DeliveryErrorCode.SMTP_FAILURE.value,
                error_message=f"SMTP transmission failed: {exc}",
                metadata={"recipients": recipients, "host": smtp_host},
            )

    def _dispatch_slack(
        self,
        report: Dict[str, Any],
        report_id: str,
        project_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deliver report summary card to Slack incoming webhook."""
        webhook_url = (
            config.get("slack_webhook_url")
            or config.get("webhook_url")
            or os.getenv("SLACK_WEBHOOK_URL")
            or report.get("slack_webhook_url")
        )

        if not webhook_url:
            attempt_id = record_delivery_attempt({
                "report_id": report_id,
                "project_id": project_id,
                "destination": DeliveryDestination.SLACK.value,
                "status": DeliveryStatus.SKIPPED.value,
                "error_code": DeliveryErrorCode.NO_SLACK_WEBHOOK.value,
                "error_message": "No Slack incoming webhook URL configured for project.",
                "metadata": {},
            })
            return {
                "attempt_id": attempt_id,
                "status": DeliveryStatus.SKIPPED.value,
                "destination": DeliveryDestination.SLACK.value,
                "error_code": DeliveryErrorCode.NO_SLACK_WEBHOOK.value,
            }

        payload = build_slack_blocks(report)

        # Custom HTTP poster adapter if injected
        if self._custom_http_poster:
            try:
                status_code, body = self._custom_http_poster(webhook_url, payload)
                if 200 <= status_code < 300:
                    attempt_id = record_delivery_attempt({
                        "report_id": report_id,
                        "project_id": project_id,
                        "destination": DeliveryDestination.SLACK.value,
                        "status": DeliveryStatus.SUCCESS.value,
                        "error_code": None,
                        "error_message": None,
                        "metadata": {"statusCode": status_code, "webhookUrl": webhook_url[:20] + "..."},
                    })
                    return {
                        "attempt_id": attempt_id,
                        "status": DeliveryStatus.SUCCESS.value,
                        "destination": DeliveryDestination.SLACK.value,
                        "error_code": None,
                    }
                else:
                    return self._record_failure(
                        report_id=report_id,
                        project_id=project_id,
                        destination=DeliveryDestination.SLACK.value,
                        error_code=f"{DeliveryErrorCode.SLACK_HTTP_ERROR.value}_{status_code}",
                        error_message=f"Slack webhook returned HTTP {status_code}: {body}",
                        metadata={"statusCode": status_code},
                    )
            except Exception as exc:
                return self._record_failure(
                    report_id=report_id,
                    project_id=project_id,
                    destination=DeliveryDestination.SLACK.value,
                    error_code=DeliveryErrorCode.SLACK_NETWORK_ERROR.value,
                    error_message=str(exc),
                )

        # Standard urllib POST
        try:
            req = Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                body = resp.read().decode("utf-8", errors="replace")

            if 200 <= status_code < 300:
                attempt_id = record_delivery_attempt({
                    "report_id": report_id,
                    "project_id": project_id,
                    "destination": DeliveryDestination.SLACK.value,
                    "status": DeliveryStatus.SUCCESS.value,
                    "error_code": None,
                    "error_message": None,
                    "metadata": {"statusCode": status_code, "body": body[:50]},
                })
                return {
                    "attempt_id": attempt_id,
                    "status": DeliveryStatus.SUCCESS.value,
                    "destination": DeliveryDestination.SLACK.value,
                    "error_code": None,
                }
            else:
                return self._record_failure(
                    report_id=report_id,
                    project_id=project_id,
                    destination=DeliveryDestination.SLACK.value,
                    error_code=f"{DeliveryErrorCode.SLACK_HTTP_ERROR.value}_{status_code}",
                    error_message=f"Slack webhook returned HTTP {status_code}: {body}",
                    metadata={"statusCode": status_code},
                )
        except HTTPError as e:
            return self._record_failure(
                report_id=report_id,
                project_id=project_id,
                destination=DeliveryDestination.SLACK.value,
                error_code=f"{DeliveryErrorCode.SLACK_HTTP_ERROR.value}_{e.code}",
                error_message=f"Slack HTTP error {e.code}: {e.reason}",
                metadata={"statusCode": e.code},
            )
        except (URLError, TimeoutError, Exception) as exc:
            return self._record_failure(
                report_id=report_id,
                project_id=project_id,
                destination=DeliveryDestination.SLACK.value,
                error_code=DeliveryErrorCode.SLACK_NETWORK_ERROR.value,
                error_message=f"Slack connection failed: {exc}",
            )

    def _record_failure(
        self,
        report_id: str,
        project_id: str,
        destination: str,
        error_code: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a failed delivery attempt."""
        logger.warning(
            "Report delivery failed. Report: %s, Destination: %s, Code: %s, Error: %s",
            report_id, destination, error_code, error_message,
        )
        attempt_id = record_delivery_attempt({
            "report_id": report_id,
            "project_id": project_id,
            "destination": destination,
            "status": DeliveryStatus.FAILED.value,
            "error_code": error_code,
            "error_message": error_message,
            "metadata": metadata or {},
        })
        return {
            "attempt_id": attempt_id,
            "status": DeliveryStatus.FAILED.value,
            "destination": destination,
            "error_code": error_code,
            "error_message": error_message,
        }


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def dispatch_report(
    report: Dict[str, Any],
    destinations: List[str],
    project_config: Optional[Dict[str, Any]] = None,
    dispatcher: Optional[DeliveryDispatcher] = None,
) -> Dict[str, Dict[str, Any]]:
    """Convenience function to dispatch report using default or custom dispatcher."""
    active_dispatcher = dispatcher or DeliveryDispatcher()
    return active_dispatcher.dispatch(report, destinations, project_config)
