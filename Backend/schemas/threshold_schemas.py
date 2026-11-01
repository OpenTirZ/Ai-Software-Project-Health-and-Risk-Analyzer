"""
Pydantic schemas for Project Health & Risk Threshold Management.

Defines:
  - Default threshold values (stale PR > 48h, stale issue > 14 days, workload imbalance ratio > 3.0, bus factor > 0.60)
  - Input validation schemas with reasonable upper and lower bounds
  - Response schemas for threshold retrieval and updates
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Default Constants
# ---------------------------------------------------------------------------

DEFAULT_STALE_PR_HOURS: int = 48
DEFAULT_STALE_ISSUE_DAYS: int = 14
DEFAULT_WORKLOAD_IMBALANCE_RATIO: float = 3.0
DEFAULT_BUS_FACTOR_THRESHOLD: float = 0.60


class ThresholdConfig(BaseModel):
    """Configuration model holding the project health & risk thresholds."""

    stale_pr_hours: int = Field(
        default=DEFAULT_STALE_PR_HOURS,
        ge=1,
        le=720,
        description="Hours after which an open PR with no activity is flagged as stale (1 to 720 hours / 30 days).",
    )
    stale_issue_days: int = Field(
        default=DEFAULT_STALE_ISSUE_DAYS,
        ge=1,
        le=365,
        description="Days after which an open issue with no activity is flagged as stale (1 to 365 days).",
    )
    workload_imbalance_ratio: float = Field(
        default=DEFAULT_WORKLOAD_IMBALANCE_RATIO,
        gt=1.0,
        le=20.0,
        description="Ratio of highest contributor activity to team median before workload imbalance is flagged (1.01 to 20.0).",
    )
    bus_factor_threshold: float = Field(
        default=DEFAULT_BUS_FACTOR_THRESHOLD,
        gt=0.0,
        le=1.0,
        description="Proportion of total commits by a single contributor that flags a bus factor risk (0.01 to 1.0, e.g. 0.60 for 60%).",
    )

    @field_validator("stale_pr_hours")
    @classmethod
    def validate_stale_pr_hours(cls, v: int) -> int:
        if v < 1:
            raise ValueError("stale_pr_hours must be a positive integer greater than 0.")
        if v > 720:
            raise ValueError("stale_pr_hours cannot exceed 720 hours (30 days).")
        return v

    @field_validator("stale_issue_days")
    @classmethod
    def validate_stale_issue_days(cls, v: int) -> int:
        if v < 1:
            raise ValueError("stale_issue_days must be a positive integer greater than 0.")
        if v > 365:
            raise ValueError("stale_issue_days cannot exceed 365 days.")
        return v

    @field_validator("workload_imbalance_ratio")
    @classmethod
    def validate_workload_ratio(cls, v: float) -> float:
        if v <= 1.0:
            raise ValueError("workload_imbalance_ratio must be strictly greater than 1.0.")
        if v > 20.0:
            raise ValueError("workload_imbalance_ratio cannot exceed 20.0.")
        return round(float(v), 2)

    @field_validator("bus_factor_threshold")
    @classmethod
    def validate_bus_factor(cls, v: float) -> float:
        if v <= 0.0 or v > 1.0:
            raise ValueError("bus_factor_threshold must be between 0.01 and 1.0 (e.g. 0.60 for 60%).")
        return round(float(v), 2)


class UpdateThresholdsRequest(BaseModel):
    """Payload for updating project thresholds (PUT /api/projects/{id}/thresholds)."""

    stale_pr_hours: Optional[int] = Field(
        None,
        ge=1,
        le=720,
        description="Hours after which a PR is stale (1 to 720 hours).",
    )
    stale_issue_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Days after which an issue is stale (1 to 365 days).",
    )
    workload_imbalance_ratio: Optional[float] = Field(
        None,
        gt=1.0,
        le=20.0,
        description="Ratio of highest contributor activity to median (1.01 to 20.0).",
    )
    bus_factor_threshold: Optional[float] = Field(
        None,
        gt=0.0,
        le=1.0,
        description="Bus factor threshold proportion (0.01 to 1.0).",
    )

    @field_validator("stale_pr_hours")
    @classmethod
    def validate_stale_pr_hours(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1:
                raise ValueError("stale_pr_hours must be a positive integer greater than 0.")
            if v > 720:
                raise ValueError("stale_pr_hours cannot exceed 720 hours (30 days).")
        return v

    @field_validator("stale_issue_days")
    @classmethod
    def validate_stale_issue_days(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1:
                raise ValueError("stale_issue_days must be a positive integer greater than 0.")
            if v > 365:
                raise ValueError("stale_issue_days cannot exceed 365 days.")
        return v

    @field_validator("workload_imbalance_ratio")
    @classmethod
    def validate_workload_ratio(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if v <= 1.0:
                raise ValueError("workload_imbalance_ratio must be strictly greater than 1.0.")
            if v > 20.0:
                raise ValueError("workload_imbalance_ratio cannot exceed 20.0.")
            return round(float(v), 2)
        return v

    @field_validator("bus_factor_threshold")
    @classmethod
    def validate_bus_factor(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if v <= 0.0 or v > 1.0:
                raise ValueError("bus_factor_threshold must be between 0.01 and 1.0 (e.g. 0.60 for 60%).")
            return round(float(v), 2)
        return v


class ThresholdsResponse(BaseModel):
    """Response returned when querying or updating project thresholds."""

    project_id: str = Field(..., description="ID of the associated project.")
    thresholds: ThresholdConfig = Field(..., description="Active project thresholds.")
    is_customized: bool = Field(
        default=False,
        description="True if thresholds have been explicitly customized, False if using system defaults.",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when thresholds were last updated (UTC).",
    )
