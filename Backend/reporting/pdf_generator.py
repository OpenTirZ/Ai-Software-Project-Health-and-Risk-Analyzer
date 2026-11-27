from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa


TEMPLATE_DIR = Path(__file__).parent / "templates"
ASSETS_DIR = Path(__file__).parent / "assets"

environment = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _ensure_report_assets() -> Dict[str, str]:
    """
    Ensure header logo, cover background, and inner background graphics exist on disk.
    Generates them dynamically using Pillow if they do not exist.
    Returns a dictionary of normalized forward-slash file paths for xhtml2pdf.
    """
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    header_logo_file = ASSETS_DIR / "kavach_logo.png"
    cover_bg_file = ASSETS_DIR / "cover_bg.png"
    inner_bg_file = ASSETS_DIR / "inner_bg.png"
    watermark_file = ASSETS_DIR / "kavach_watermark.png"

    needed = [header_logo_file, cover_bg_file, inner_bg_file]
    if any(not p.exists() for p in needed):
        root_dir = Path(__file__).resolve().parent.parent.parent
        candidates = [
            root_dir / "Frontend" / "public" / "assets" / "kavach-logo.png",
            root_dir / "Frontend" / "dist" / "assets" / "kavach-logo.png",
            root_dir / "Frontend" / "public" / "favicon.png",
        ]
        src_logo = next((p for p in candidates if p.exists()), None)
        if src_logo:
            try:
                from PIL import Image, ImageDraw

                logo_raw = Image.open(src_logo).convert("RGBA")
                bbox = logo_raw.getbbox()
                logo_cropped = logo_raw.crop(bbox) if bbox else logo_raw
                max_dim = max(logo_cropped.width, logo_cropped.height)
                logo_sq = Image.new("RGBA", (max_dim, max_dim), (255, 255, 255, 0))
                logo_sq.paste(
                    logo_cropped,
                    ((max_dim - logo_cropped.width) // 2, (max_dim - logo_cropped.height) // 2),
                )

                if not header_logo_file.exists():
                    hl = logo_sq.resize((512, 512), Image.Resampling.LANCZOS)
                    hl.save(header_logo_file, "PNG")

                w2, h2 = 2480, 3508
                w_final, h_final = 1240, 1754
                DARK_TEAL = (0, 77, 64, 255)
                PRIMARY_TEAL = (11, 107, 99, 255)
                ACCENT_MINT = (205, 239, 230, 255)
                WHITE = (255, 255, 255, 255)

                # Generate cover background if missing
                if not cover_bg_file.exists():
                    img_cov = Image.new("RGBA", (w2, h2), WHITE)
                    draw_cov = ImageDraw.Draw(img_cov)
                    p_l1 = [(0, 0), (int(w2 * 0.32), 0)]
                    for t in range(101):
                        u = t / 100
                        bx = (1 - u) ** 2 * (w2 * 0.32) + 2 * (1 - u) * u * (w2 * 0.14)
                        by = 2 * (1 - u) * u * (h2 * 0.07) + u**2 * (h2 * 0.09)
                        p_l1.append((int(bx), int(by)))
                    p_l1.append((0, 0))
                    draw_cov.polygon(p_l1, fill=DARK_TEAL)

                    p_b1 = [(w2, h2), (w2, int(h2 * 0.74))]
                    for t in range(101):
                        u = t / 100
                        bx = (1 - u) ** 2 * w2 + 2 * (1 - u) * u * (w2 * 0.72) + u**2 * (w2 * 0.34)
                        by = (1 - u) ** 2 * (h2 * 0.74) + 2 * (1 - u) * u * (h2 * 0.92) + u**2 * h2
                        p_b1.append((int(bx), int(by)))
                    p_b1.append((w2, h2))
                    draw_cov.polygon(p_b1, fill=DARK_TEAL)

                    wm_size = 1150
                    r, g, b, alpha = logo_sq.split()
                    alpha_subtle = alpha.point(lambda p: int(p * 0.065))
                    wm_logo = Image.merge("RGBA", (r, g, b, alpha_subtle)).resize(
                        (wm_size, wm_size), Image.Resampling.LANCZOS
                    )
                    img_cov.paste(
                        wm_logo,
                        ((w2 - wm_size) // 2 + 80, (h2 - wm_size) // 2 + 70),
                        wm_logo,
                    )
                    cov_final = img_cov.resize((w_final, h_final), Image.Resampling.LANCZOS)
                    cov_final.save(cover_bg_file, "PNG")

                # Generate inner background if missing
                if not inner_bg_file.exists():
                    img_in = Image.new("RGBA", (w2, h2), WHITE)
                    draw_in = ImageDraw.Draw(img_in)
                    p_top = [(0, 0), (int(w2 * 0.18), 0)]
                    for t in range(101):
                        u = t / 100
                        bx = (1 - u) ** 2 * (w2 * 0.18) + 2 * (1 - u) * u * (w2 * 0.08)
                        by = 2 * (1 - u) * u * (h2 * 0.025) + u**2 * (h2 * 0.035)
                        p_top.append((int(bx), int(by)))
                    p_top.append((0, 0))
                    draw_in.polygon(p_top, fill=PRIMARY_TEAL)

                    p_bot = [(w2, h2), (w2, int(h2 * 0.96))]
                    for t in range(101):
                        u = t / 100
                        bx = (1 - u) ** 2 * w2 + 2 * (1 - u) * u * (w2 * 0.92) + u**2 * (w2 * 0.80)
                        by = (1 - u) ** 2 * (h2 * 0.96) + 2 * (1 - u) * u * (h2 * 0.99) + u**2 * h2
                        p_bot.append((int(bx), int(by)))
                    p_bot.append((w2, h2))
                    draw_in.polygon(p_bot, fill=PRIMARY_TEAL)

                    wm_size_in = 950
                    r, g, b, alpha = logo_sq.split()
                    alpha_subtle_in = alpha.point(lambda p: int(p * 0.045))
                    wm_logo_in = Image.merge("RGBA", (r, g, b, alpha_subtle_in)).resize(
                        (wm_size_in, wm_size_in), Image.Resampling.LANCZOS
                    )
                    img_in.paste(
                        wm_logo_in,
                        ((w2 - wm_size_in) // 2, (h2 - wm_size_in) // 2 + 50),
                        wm_logo_in,
                    )
                    in_final = img_in.resize((w_final, h_final), Image.Resampling.LANCZOS)
                    in_final.save(inner_bg_file, "PNG")

            except Exception:
                pass

    return {
        "header_logo_path": str(header_logo_file).replace("\\", "/") if header_logo_file.exists() else "",
        "cover_bg_path": str(cover_bg_file).replace("\\", "/") if cover_bg_file.exists() else "",
        "inner_bg_path": str(inner_bg_file).replace("\\", "/") if inner_bg_file.exists() else "",
        "watermark_path": str(inner_bg_file).replace("\\", "/") if inner_bg_file.exists() else "",
    }


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

    assets = _ensure_report_assets()

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
        "header_logo_path": assets["header_logo_path"],
        "cover_bg_path": assets["cover_bg_path"],
        "inner_bg_path": assets["inner_bg_path"],
        "watermark_path": assets["watermark_path"],
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
