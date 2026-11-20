
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from io import BytesIO

from Backend.reporting import pdf_generator
from Backend.reporting.pdf_generator import (
    _as_dict,
    _as_list,
    _format_date,
    _format_label,
    _get_metric_sections,
    _get_detail_rows,
    _get_sprint_progress,
    _normalize_recommendation,
    generate_report_pdf,
)


@pytest.fixture
def sample_report():
    return {
        "generatedAt": "2026-11-20T10:30:00+00:00",
        "summary": "The project is progressing well.",
        "risks": ["Delayed tasks"],
        "recommendations": [
            "Review pending tasks",
            {
                "title": "Improve testing",
                "priority": "High",
                "action": "Add more unit tests",
            },
        ],
        "metricsSnapshot": {
            "project_health": {
                "score": 78,
                "status": "healthy",
            },
            "sprint_report": {
                "metrics": {
                    "total_milestones": 5,
                    "closed_milestones": 3,
                    "open_milestones": 2,
                    "average_completion_pct": 65,
                    "overdue_milestones": 1,
                }
            },
            "bottleneck_prs": [
                {
                    "title": "Review pending PR",
                    "days_open": 8,
                    "status": "open",
                }
            ],
            "contributors": [
                {
                    "name": "Developer A",
                    "commits": 12,
                    "pull_requests": 4,
                }
            ],
            "milestones": [
                {
                    "name": "Sprint 1",
                    "completion": 80,
                }
            ],
        },
    }


# -------------------- Basic helper tests --------------------


def test_as_dict_with_dictionary():
    value = {"score": 80}
    assert _as_dict(value) == value


@pytest.mark.parametrize("value", [None, [], "text", 10])
def test_as_dict_with_invalid_input(value):
    assert _as_dict(value) == {}


def test_as_list_with_list():
    value = [1, 2, 3]
    assert _as_list(value) == value


@pytest.mark.parametrize("value", [None, {}, "text", 10])
def test_as_list_with_invalid_input(value):
    assert _as_list(value) == []


# -------------------- Date and label tests --------------------


def test_format_date_with_valid_date():
    result = _format_date("2026-11-20T10:30:00+00:00")
    assert "20 November 2026" in result


def test_format_date_with_missing_value():
    assert _format_date(None) == "Not available"


def test_format_date_with_invalid_value():
    assert _format_date("invalid-date") == "invalid-date"


def test_format_label_replaces_underscores_and_hyphens():
    assert _format_label("project_health-score") == "Project Health Score"


# -------------------- Metric section tests --------------------


def test_get_metric_sections_with_nested_metrics():
    result = _get_metric_sections({
        "sprint_report": {
            "metrics": {
                "total_milestones": 5,
                "completion": 75,
            }
        }
    })

    assert len(result) == 1
    assert result[0]["name"] == "Sprint Report"
    assert len(result[0]["values"]) == 2


def test_get_metric_sections_with_direct_metrics():
    result = _get_metric_sections({
        "project_health": {
            "score": 80,
            "status": "healthy",
        }
    })

    assert len(result) == 1
    assert result[0]["name"] == "Project Health"


def test_get_metric_sections_skips_detail_collections():
    result = _get_metric_sections({
        "contributors": [{"name": "Developer A"}],
        "bottleneck_prs": [{"title": "Pending PR"}],
        "milestones": [{"name": "Sprint 1"}],
    })

    assert result == []


def test_get_metric_sections_ignores_non_dictionary_values():
    result = _get_metric_sections({
        "invalid_section": "not a dictionary",
        "valid_section": {
            "score": 80,
        },
    })

    assert len(result) == 1
    assert result[0]["name"] == "Valid Section"


# -------------------- Detail row tests --------------------


def test_get_detail_rows_with_dictionary_items():
    result = _get_detail_rows([
        {
            "name": "Developer A",
            "commits": 12,
        }
    ])

    assert len(result) == 1
    assert len(result[0]) == 2


def test_get_detail_rows_with_string_items():
    result = _get_detail_rows(["Pending review"])

    assert result == [[
        {"label": "Details", "value": "Pending review"}
    ]]


def test_get_detail_rows_with_empty_list():
    assert _get_detail_rows([]) == []


def test_get_detail_rows_ignores_empty_dictionary():
    assert _get_detail_rows([{}]) == []


# -------------------- Sprint progress tests --------------------


def test_get_sprint_progress_with_complete_metrics():
    result = _get_sprint_progress({
        "sprint_report": {
            "metrics": {
                "total_milestones": 5,
                "closed_milestones": 3,
                "open_milestones": 2,
                "average_completion_pct": 65,
                "overdue_milestones": 1,
            }
        }
    })

    assert "Total milestones: 5" in result
    assert "Closed: 3" in result
    assert "Open: 2" in result
    assert "Average completion: 65%" in result
    assert "Overdue: 1" in result


def test_get_sprint_progress_with_partial_metrics():
    result = _get_sprint_progress({
        "sprint_report": {
            "metrics": {
                "total_milestones": 5,
            }
        }
    })

    assert result == "Total milestones: 5"


def test_get_sprint_progress_without_metrics():
    assert _get_sprint_progress({}) is None


def test_get_sprint_progress_with_invalid_metrics():
    assert _get_sprint_progress({
        "sprint_report": "invalid"
    }) is None


# -------------------- Recommendation tests --------------------


def test_normalize_recommendation_with_string():
    result = _normalize_recommendation("Review pending tasks")

    assert result["title"] == "Review pending tasks"
    assert result["action"] == "Review pending tasks"
    assert result["priority"] == "Not specified"


def test_normalize_recommendation_with_complete_dictionary():
    result = _normalize_recommendation({
        "title": "Improve testing",
        "priority": "High",
        "action": "Add unit tests",
    })

    assert result == {
        "title": "Improve testing",
        "priority": "High",
        "action": "Add unit tests",
    }


def test_normalize_recommendation_with_recommendation_field():
    result = _normalize_recommendation({
        "recommendation": "Review pull requests",
    })

    assert result["action"] == "Review pull requests"


def test_normalize_recommendation_with_description_field():
    result = _normalize_recommendation({
        "description": "Improve code quality",
    })

    assert result["action"] == "Improve code quality"


def test_normalize_recommendation_with_empty_dictionary():
    result = _normalize_recommendation({})

    assert result["priority"] == "Not specified"
    assert result["action"] == "No action details provided"


def test_normalize_recommendation_with_other_value():
    result = _normalize_recommendation(123)

    assert result["title"] == "123"
    assert result["action"] == "123"


# -------------------- PDF generation tests --------------------


def test_generate_pdf_returns_valid_pdf(sample_report):
    pdf_bytes = generate_report_pdf(
        sample_report,
        project_name="Sample Project",
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_generated_pdf_contains_required_sections(sample_report):
    pdf_bytes = generate_report_pdf(
        sample_report,
        project_name="Sample Project",
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    required_sections = [
        "Sample Project",
        "Executive Summary",
        "Bottlenecks",
        "AI Recommendations",
    ]

    for section in required_sections:
        assert section.lower() in text.lower()


def test_generated_pdf_contains_report_data(sample_report):
    pdf_bytes = generate_report_pdf(
        sample_report,
        project_name="Sample Project",
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "78" in text
    assert "healthy" in text.lower()
    assert "Review pending PR" in text
    assert "Developer A" in text
    assert "Review pending tasks" in text


def test_generated_pdf_contains_sprint_progress(sample_report):
    pdf_bytes = generate_report_pdf(sample_report)

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Total milestones: 5" in text
    assert "Closed: 3" in text
    assert "Overdue: 1" in text


def test_generated_pdf_contains_reporting_period_when_missing(sample_report):
    pdf_bytes = generate_report_pdf(sample_report)

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Not specified" in text


def test_generated_pdf_contains_provided_reporting_period(sample_report):
    sample_report["reportingPeriod"] = "2026-11-01"

    pdf_bytes = generate_report_pdf(sample_report)

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "November 2026" in text


def test_generate_pdf_handles_missing_optional_data():
    report = {
        "generatedAt": "2026-11-20T10:30:00+00:00",
        "summary": "Basic report",
        "metricsSnapshot": {},
        "recommendations": [],
        "risks": [],
    }

    pdf_bytes = generate_report_pdf(report)

    assert pdf_bytes.startswith(b"%PDF")


def test_generate_pdf_handles_missing_metrics():
    report = {
        "summary": "Report without metrics",
    }

    pdf_bytes = generate_report_pdf(report)

    assert pdf_bytes.startswith(b"%PDF")


def test_generate_pdf_rejects_invalid_report():
    with pytest.raises(ValueError, match="Report must be a dictionary"):
        generate_report_pdf(None)


def test_generate_pdf_rejects_list_input():
    with pytest.raises(ValueError, match="Report must be a dictionary"):
        generate_report_pdf([])


def test_generate_pdf_raises_when_pdf_creation_fails(
    sample_report,
    monkeypatch,
):
    def fake_create_pdf(**kwargs):
        return SimpleNamespace(err=1)

    monkeypatch.setattr(
        pdf_generator.pisa,
        "CreatePDF",
        fake_create_pdf,
    )

    with pytest.raises(ValueError, match="Failed to generate PDF"):
        generate_report_pdf(sample_report)
