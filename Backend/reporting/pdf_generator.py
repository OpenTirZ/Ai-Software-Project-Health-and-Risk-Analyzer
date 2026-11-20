
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa


TEMPLATE_DIR = Path(__file__).parent / "templates"

environment = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _format_date(value: Any) -> str:
    if not value:
        return "Not available"

    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.strftime("%d %B %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return str(value)


def _format_label(value: Any) -> str:
    return str(value).replace("_", " ").replace("-", " ").title()


def _get_metric_sections(metrics: Dict[str, Any]) -> list:
    sections = []

    for name, data in metrics.items():
        if name in {"contributors", "bottleneck_prs", "milestones"}:
            continue

        if not isinstance(data, dict):
            continue

        values = data.get("metrics", data)

        if not isinstance(values, dict):
            continue

        sections.append({
            "name": _format_label(name),
            "values": [
                {
                    "label": _format_label(key),
                    "value": value,
                }
                for key, value in values.items()
                if isinstance(value, (str, int, float, bool))
                and value is not None
            ],
        })

    return sections


def _get_detail_rows(items: list) -> list:
    rows = []

    for item in items:
        if isinstance(item, dict):
            rows.append([
                {
                    "label": _format_label(key),
                    "value": value,
                }
                for key, value in item.items()
                if isinstance(value, (str, int, float, bool))
                and value is not None
            ])
        else:
            rows.append([
                {"label": "Details", "value": str(item)}
            ])

    return [row for row in rows if row]


def _get_sprint_progress(metrics: Dict[str, Any]) -> Optional[str]:
    sprint = _as_dict(metrics.get("sprint_report"))
    sprint_metrics = _as_dict(sprint.get("metrics"))

    total = sprint_metrics.get("total_milestones")
    closed = sprint_metrics.get("closed_milestones")
    opened = sprint_metrics.get("open_milestones")
    average = sprint_metrics.get("average_completion_pct")
    overdue = sprint_metrics.get("overdue_milestones")

    if all(value is None for value in (total, closed, opened, average, overdue)):
        return None

    parts = []

    if total is not None:
        parts.append(f"Total milestones: {total}")
    if closed is not None:
        parts.append(f"Closed: {closed}")
    if opened is not None:
        parts.append(f"Open: {opened}")
    if average is not None:
        parts.append(f"Average completion: {average}%")
    if overdue is not None:
        parts.append(f"Overdue: {overdue}")

    return " | ".join(parts)


def _normalize_recommendation(item: Any) -> Dict[str, str]:
    if isinstance(item, str):
        return {
            "title": item,
            "priority": "Not specified",
            "action": item,
        }

    if isinstance(item, dict):
        action = (
            item.get("action")
            or item.get("recommendation")
            or item.get("description")
            or "No action details provided"
        )

        return {
            "title": str(item.get("title") or action),
            "priority": str(
                item.get("priority") or item.get("severity") or "Not specified"
            ),
            "action": str(action),
        }

    return {
        "title": str(item),
        "priority": "Not specified",
        "action": str(item),
    }


def generate_report_pdf(
    report: Dict[str, Any],
    project_name: Optional[str] = None,
) -> bytes:
    if not isinstance(report, dict):
        raise ValueError("Report must be a dictionary.")

    metrics = _as_dict(report.get("metricsSnapshot"))
    health = _as_dict(metrics.get("project_health"))

    recommendations = [
        _normalize_recommendation(item)
        for item in _as_list(report.get("recommendations"))
    ]

    context = {
        "project_name": project_name or "Project Health Report",
        "generated_at": _format_date(report.get("generatedAt")),
        "health_score": health.get("score"),
        "health_status": str(
            health.get("status") or "Not available"
        ).replace("_", " ").title(),
        "executive_summary": (
            report.get("summary") or "No executive summary available."
        ),
        "risks": _as_list(report.get("risks")),
        "bottlenecks": _get_detail_rows(
            _as_list(metrics.get("bottleneck_prs"))
        ),
        "contributors": _get_detail_rows(
            _as_list(metrics.get("contributors"))
        ),
        "recommendations": recommendations,
        "metric_sections": _get_metric_sections(metrics),
        "sprint_progress": _get_sprint_progress(metrics),
        "milestones": _get_detail_rows(
            _as_list(metrics.get("milestones"))
        ),
        "reporting_period": (
            _format_date(report.get("reportingPeriod"))
            if report.get("reportingPeriod")
            else "Not specified"
        ),
    }

    template = environment.get_template("pdf_report.html")
    html = template.render(**context)

    output = BytesIO()
    result = pisa.CreatePDF(
        src=html,
        dest=output,
        encoding="utf-8",
    )

    if result.err:
        raise ValueError("Failed to generate PDF report.")

    pdf_bytes = output.getvalue()

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Generated PDF is invalid.")

    return pdf_bytes
