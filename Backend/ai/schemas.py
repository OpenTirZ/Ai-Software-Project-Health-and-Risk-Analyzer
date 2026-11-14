"""
Strict Pydantic Output Schemas for LLM Responses.
--------------------------------------------------
Defines validated, typed output models for:
  - ExplanationSchema: Plain-language explanations of project risk flags/indicators.
  - RecommendationSchema: Advisory engineering recommendations grounded in computed metrics.
  - ReportResponseSchema: Structured project health status reports.

Design Principles:
  1. Strict Structure: 'extra="forbid"' prevents hallucinated fields from being accepted.
  2. Grounded Evidence: Explanations require observable contributing metrics and evidence points.
  3. Non-Prescriptive: Recommendations are explicitly marked advisory and cannot mandate actions.
  4. Data Freshness & Uncertainty: Schemas require disclaimers and explicit handling of missing inputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Allowed severities for flag explanations
SeverityLevel = Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Allowed priorities for recommendations
PriorityLevel = Literal["LOW", "MEDIUM", "HIGH"]

# Standard Project Health Statuses (aligning with health_summary.py)
HealthStatus = Literal["Good", "Caution", "At Risk", "Insufficient Data"]


class ExplanationSchema(BaseModel):
    """
    Schema for plain-language explanations of detected project risk flags.
    Enforces that explanations link directly to observable indicators.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    indicator_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Name of the detected flag or metric indicator (e.g. 'aging_prs', 'workload_imbalance').",
    )
    severity: SeverityLevel = Field(
        ...,
        description="Severity level of the flag: INFO, LOW, MEDIUM, HIGH, or CRITICAL.",
    )
    explanation: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Plain-language explanation of what this flag means for the team.",
    )
    contributing_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key numerical values or thresholds that triggered this flag.",
    )
    source_period: Optional[str] = Field(
        None,
        max_length=120,
        description="Time period from which data was analyzed (e.g., 'Last 14 days', 'Sprint 2').",
    )
    evidence: List[str] = Field(
        ...,
        min_length=1,
        description="List of observable evidence points (e.g. PR numbers, commit counts).",
    )
    uncertainty_or_caveats: Optional[str] = Field(
        None,
        max_length=1000,
        description="Disclosure of missing telemetry, partial data, or proxy limitations.",
    )

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                return v_upper
        raise ValueError(
            f"Invalid severity '{v}'. Must be one of: INFO, LOW, MEDIUM, HIGH, CRITICAL."
        )


class RecommendationSchema(BaseModel):
    """
    Schema for actionable advisory engineering recommendations.
    Enforces the advisory disclaimer principle (system does not make automated decisions).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Category of the recommendation (e.g., 'code_review', 'workload_balance', 'milestone_pacing').",
    )
    condition: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The specific observed condition or bottleneck this recommendation addresses.",
    )
    action: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Actionable, pragmatic engineering suggestion for team leads or engineers.",
    )
    rationale: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Why this action is suggested based on computed metrics and project health.",
    )
    priority: PriorityLevel = Field(
        ...,
        description="Priority level: LOW, MEDIUM, or HIGH.",
    )
    target_role: Optional[str] = Field(
        default="Team Lead",
        max_length=100,
        description="Stakeholder group primarily concerned (e.g. 'Team Lead', 'Project Manager', 'Reviewer').",
    )
    is_advisory: bool = Field(
        default=True,
        description="Affirmation that this recommendation is strictly advisory and not an automated action.",
    )
    disclaimer: str = Field(
        default="Recommendations are advisory. Final decisions remain with the engineering team.",
        min_length=10,
        max_length=500,
        description="Human-in-the-loop governance disclaimer.",
    )

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in {"LOW", "MEDIUM", "HIGH"}:
                return v_upper
        raise ValueError(
            f"Invalid priority '{v}'. Must be one of: LOW, MEDIUM, HIGH."
        )

    @field_validator("is_advisory")
    @classmethod
    def enforce_advisory(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "is_advisory must be True. System recommendations cannot be mandatory or autonomous."
            )
        return True


class ReportResponseSchema(BaseModel):
    """
    Schema for LLM-generated project status reports.
    Synthesizes health status, progress, risks, explanations, and recommendations.
    Strictly forbids hallucinated extra keys.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_name: Optional[str] = Field(
        None,
        max_length=150,
        description="Name of the software project being reported on.",
    )
    executive_summary: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Comprehensive narrative summarizing project health, velocity, and delivery posture.",
    )
    health_status: HealthStatus = Field(
        ...,
        description="Overall project health classification: 'Good', 'Caution', 'At Risk', or 'Insufficient Data'.",
    )
    health_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Composite health index from 0.0 to 100.0 (None if insufficient data).",
    )
    key_highlights: List[str] = Field(
        default_factory=list,
        description="Bullet points of positive progress, steady velocity, or resolved bottlenecks.",
    )
    identified_risks: List[str] = Field(
        default_factory=list,
        description="Bullet points of active delivery blockers, workload skews, or stale items.",
    )
    flag_explanations: List[ExplanationSchema] = Field(
        default_factory=list,
        description="Detailed plain-language explanations of each detected risk flag.",
    )
    recommendations: List[RecommendationSchema] = Field(
        default_factory=list,
        description="Actionable, advisory engineering recommendations for detected risks.",
    )
    data_freshness_disclaimer: Optional[str] = Field(
        None,
        max_length=500,
        description="Timestamp or statement indicating telemetry freshness and last sync time.",
    )
    missing_data_caveats: List[str] = Field(
        default_factory=list,
        description="Explicit enumeration of missing or incomplete telemetry data sources.",
    )

    @field_validator("health_status", mode="before")
    @classmethod
    def normalize_health_status(cls, v: Any) -> str:
        if isinstance(v, str):
            v_clean = v.strip()
            # Normalize title/case variations
            mapping = {
                "good": "Good",
                "healthy": "Good",
                "caution": "Caution",
                "warning": "Caution",
                "at risk": "At Risk",
                "at_risk": "At Risk",
                "critical": "At Risk",
                "insufficient data": "Insufficient Data",
                "insufficient_data": "Insufficient Data",
            }
            mapped = mapping.get(v_clean.lower())
            if mapped:
                return mapped
        raise ValueError(
            f"Invalid health_status '{v}'. Must be one of: 'Good', 'Caution', 'At Risk', 'Insufficient Data'."
        )

