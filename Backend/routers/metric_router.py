"""
FastAPI router for Project Health and Risk Metrics.
---------------------------------------------------
Task: TASK-SP2-01 (Shah Varshil - Backend Lead)

Endpoints:
    GET /api/projects/{id}/health-summary
        Returns aggregated composite health score (0-100), overall status
        (Good / Caution / At Risk / Insufficient Data), data freshness,
        active risk flags, and summary statement.

    GET /api/projects/{id}/metrics/breakdown
        Returns granular indicator breakdown across bottlenecks, workload,
        stale issues, and schedule risk, with normalized weights and evidence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId, errors
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from Backend.auth.dependencies import get_current_user
from Backend.auth.roles import Role
from Backend.analysis.health_summary import (
    build_health_summary,
    build_metrics_breakdown,
)
from Backend.persistence import (
    DatabaseError,
    get_project,
    get_project_commits,
    get_project_contributors,
    get_project_issues,
    get_project_pull_requests,
    get_project_sprints,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Project Health & Metrics"])


# ---------------------------------------------------------------------------
# Pydantic Schemas for OpenAPI / Swagger documentation
# ---------------------------------------------------------------------------

class FlagsCountSchema(BaseModel):
    total: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class FlagDetailSchema(BaseModel):
    id: str
    type: str
    severity: str
    message: str
    evidence: Optional[Dict[str, Any]] = None


class HealthSummaryResponse(BaseModel):
    project_id: str
    project_name: str
    health_score: Optional[float] = Field(
        None, description="0-100 composite health score, or null if insufficient data"
    )
    status: str = Field(
        ..., description="Aggregated status: Good, Caution, At Risk, or Insufficient Data"
    )
    last_synced_at: Optional[str] = None
    data_freshness: str = Field(..., description="fresh, stale, or unknown")
    data_availability: Dict[str, str] = Field(
        ..., description="Status per telemetry source: available or insufficient_data"
    )
    summary_statement: str
    flags_count: FlagsCountSchema
    active_flags: List[FlagDetailSchema]
    evaluated_at: str


class IndicatorDetailSchema(BaseModel):
    score: Optional[float] = None
    status: str
    data_status: str
    weight: float
    details: Dict[str, Any]
    flags: List[Dict[str, Any]]


class MetricsBreakdownResponse(BaseModel):
    project_id: str
    project_name: str
    health_score: Optional[float] = None
    status: str
    evaluated_at: str
    weights_used: Dict[str, float]
    indicators: Dict[str, IndicatorDetailSchema]


# ---------------------------------------------------------------------------
# Authorization & Security Helpers
# ---------------------------------------------------------------------------

def _parse_project_id(id_str: str) -> str:
    """Validate project ID format. Raises 400 Bad Request on invalid format."""
    try:
        ObjectId(id_str)
        return id_str
    except (errors.InvalidId, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format.",
        )


def _get_user_id(current_user: dict) -> str:
    """Extract string user ID from authenticated token payload."""
    user_id = current_user.get("_id") or current_user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )
    return str(user_id)


def _is_authorized_for_project(project: dict, current_user: dict) -> bool:
    """Check if current user is an admin, owner, or assigned project member."""
    user_role = current_user.get("role", "")
    if user_role in (Role.ADMIN.value, "admin"):
        return True

    user_id = _get_user_id(current_user)
    owner_id = project.get("ownerId") or project.get("owner_id")
    if owner_id and str(owner_id) == user_id:
        return True

    members = project.get("members", [])
    if isinstance(members, list):
        for m in members:
            if isinstance(m, dict):
                m_uid = m.get("userId") or m.get("user_id")
                if m_uid and str(m_uid) == user_id:
                    return True
            elif str(m) == user_id:
                return True

    return False


def _fetch_project_data(project_id: str, current_user: dict) -> tuple[dict, list, list, list, list, list]:
    """
    Validate ID, verify user authorization, and safely fetch telemetry.
    Returns: (project, commits, contributors, pull_requests, issues, sprints)
    """
    clean_id = _parse_project_id(project_id)

    try:
        project = get_project(clean_id)
    except DatabaseError as e:
        logger.error("Database failure fetching project %s: %s", clean_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if not _is_authorized_for_project(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this project.",
        )

    # Safely fetch telemetry datasets; if any collection is empty or missing,
    # default to empty list so analysis engine handles 'insufficient_data'.
    try:
        commits = get_project_commits(clean_id) or []
    except Exception as e:
        logger.warning("Could not fetch commits for %s: %s", clean_id, e)
        commits = []

    try:
        contributors = get_project_contributors(clean_id) or []
    except Exception as e:
        logger.warning("Could not fetch contributors for %s: %s", clean_id, e)
        contributors = []

    try:
        pull_requests = get_project_pull_requests(clean_id) or []
    except Exception as e:
        logger.warning("Could not fetch PRs for %s: %s", clean_id, e)
        pull_requests = []

    try:
        issues = get_project_issues(clean_id) or []
    except Exception as e:
        logger.warning("Could not fetch issues for %s: %s", clean_id, e)
        issues = []

    try:
        sprints = get_project_sprints(clean_id) or []
    except Exception as e:
        logger.warning("Could not fetch sprints for %s: %s", clean_id, e)
        sprints = []

    return project, commits, contributors, pull_requests, issues, sprints


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{id}/health-summary",
    response_model=HealthSummaryResponse,
    summary="Get project health summary",
    description="Returns composite 0-100 health score, aggregated status (Good / Caution / At Risk), and active flags.",
)
def get_health_summary_endpoint(
    id: str = Path(..., description="Target project ObjectId"),
    current_user: dict = Depends(get_current_user),
):
    """
    Evaluate overall project health from observable GitHub activity and sprint telemetry.
    Gracefully handles missing or unconfigured PR/milestone data.
    """
    project, commits, contributors, pull_requests, issues, sprints = _fetch_project_data(
        id, current_user
    )

    summary = build_health_summary(
        project=project,
        commits=commits,
        contributors=contributors,
        pull_requests=pull_requests,
        issues=issues,
        sprints=sprints,
    )
    return summary


@router.get(
    "/{id}/metrics/breakdown",
    response_model=MetricsBreakdownResponse,
    summary="Get detailed metrics breakdown",
    description="Returns granular indicators (bottlenecks, workload, stale issues, schedule risk) with weights and evidence.",
)
def get_metrics_breakdown_endpoint(
    id: str = Path(..., description="Target project ObjectId"),
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve dimensional breakdown across bottlenecks, workload, stale issues, and schedule risk.
    """
    project, commits, contributors, pull_requests, issues, sprints = _fetch_project_data(
        id, current_user
    )

    breakdown = build_metrics_breakdown(
        project=project,
        commits=commits,
        contributors=contributors,
        pull_requests=pull_requests,
        issues=issues,
        sprints=sprints,
    )
    return breakdown

