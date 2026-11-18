"""
FastAPI router for AI report generation, report persistence, and report schedules.

Endpoints (all under /api/projects/{project_id}/reports):
    POST   /generate                 Run the LangGraph V2 pipeline over the project's
                                     persisted telemetry and persist a validated JSON
                                     status report.
    GET    /                         List persisted reports (newest first).
    GET    /latest                   Fetch the newest persisted report.
    GET    /{report_id}              Fetch one persisted report.
    DELETE /{report_id}              Delete one persisted report (admin/PM).

Schedules (declared before the dynamic /{report_id} route):
    POST   /schedules                Create a delivery schedule (email/slack).
    GET    /schedules                List schedules (optional status filter).
    PATCH  /schedules/{schedule_id}  Update frequency/destinations/status.
    DELETE /schedules/{schedule_id}  Delete a schedule.
    POST   /schedules/{schedule_id}/run
                                     Generate a report now and stamp the
                                     schedule's lastRun/status.

Telemetry is loaded with pipeline_v2.load_project_telemetry() and analyzed with
pipeline_v2.run_analysis(); persistence goes through Backend/persistence_reports.py.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from Backend.auth.dependencies import get_current_user
from Backend.auth.roles import Role, require_role
from Backend.persistence import DatabaseError, get_project
from Backend.persistence_reports import (
    count_project_reports,
    create_report_schedule,
    delete_report,
    delete_report_schedule,
    get_latest_project_report,
    get_project_reports,
    get_project_schedules,
    get_report,
    get_schedule,
    record_schedule_run,
    update_report_schedule,
)
from Backend.routers.project_router import _get_user_id, _is_project_member

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/reports",
    tags=["Reports & Schedules"],
)


# ---------------------------------------------------------------------------
# LangGraph V2 pipeline loader (folder is not a package; load by file path)
# ---------------------------------------------------------------------------

_PIPELINE_MODULE_NAME = "pipeline_v2_langgraph"


def _load_pipeline_v2():
    """Import pipeline_v2.py from Backend/externalservies/LangGraph by path.

    The LangGraph folder intentionally stays a plain directory (no package
    marker) so the existing standalone usage keeps working; loading through
    importlib registers the module once and reuses the compiled graph.
    """
    module = sys.modules.get(_PIPELINE_MODULE_NAME)
    if module is not None:
        return module

    langgraph_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "externalservies",
        "LangGraph",
    )
    module_path = os.path.join(langgraph_dir, "pipeline_v2.py")
    if not os.path.isfile(module_path):
        raise FileNotFoundError(f"pipeline_v2.py not found at {module_path}")

    spec = importlib.util.spec_from_file_location(_PIPELINE_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PIPELINE_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Shared authorization helper (same rules as the data-sync router)
# ---------------------------------------------------------------------------

def _require_project_member(project_id: str, current_user: dict) -> dict:
    """Require an authenticated project owner or member."""
    user_id = _get_user_id(current_user)

    project = get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if not _is_project_member(project, user_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied. You are not a member of this project.",
        )

    return project


def _generate_and_persist_report(project_id: str) -> dict:
    """Run the V2 pipeline over persisted telemetry and store the report."""
    pipeline = _load_pipeline_v2()
    telemetry = pipeline.load_project_telemetry(project_id)
    report = pipeline.run_analysis(
        telemetry.get("contributors") or [],
        telemetry.get("commits") or [],
        telemetry.get("pull_requests") or [],
        telemetry.get("issues") or [],
        telemetry.get("milestones") or [],
    )
    report_id = pipeline.export_report_to_persistence(report, project_id)
    return {"report_id": report_id, "report": report}


def _map_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReportScheduleCreate(BaseModel):
    """Payload to create a report delivery schedule."""

    frequency: Literal["daily", "weekly", "monthly"] = Field(
        description="How often the report is generated and delivered."
    )
    destinations: List[Literal["email", "slack"]] = Field(
        min_length=1,
        description="Delivery channels; at least one of email or slack.",
    )


class ReportScheduleUpdate(BaseModel):
    """Payload to update an existing schedule; omitted fields stay unchanged."""

    frequency: Optional[Literal["daily", "weekly", "monthly"]] = None
    destinations: Optional[List[Literal["email", "slack"]]] = Field(
        default=None, min_length=1
    )
    status: Optional[Literal["active", "paused", "completed", "failed"]] = None


class GeneratedReportResponse(BaseModel):
    """Response for report generation endpoints."""

    success: bool
    project_id: str
    report_id: str
    generated_at: str
    health_score: int
    health_status: str
    llm_used: bool
    report: dict


class ReportListResponse(BaseModel):
    """Paginated list of persisted report summaries."""

    success: bool
    project_id: str
    total_reports: int
    returned: int
    reports: List[dict]


class ScheduleListResponse(BaseModel):
    """List of schedules configured for a project."""

    success: bool
    project_id: str
    schedules: List[dict]


class SimpleSuccessResponse(BaseModel):
    success: bool
    detail: str


# ---------------------------------------------------------------------------
# Report generation & persistence endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=GeneratedReportResponse,
    summary="Run the LangGraph V2 analysis and persist a validated status report",
)
def generate_project_report(
    project_id: str,
    current_user: dict = Depends(
        require_role(Role.ADMIN, Role.PROJECT_MANAGER, Role.DEVELOPER)
    ),
):
    _require_project_member(project_id, current_user)
    try:
        generated = _generate_and_persist_report(project_id)
    except DatabaseError:
        raise  # handled globally as 503
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise _map_value_error(exc)

    report = generated["report"]
    health = report.get("project_health") or {}
    llm_status = report.get("llm") or {}
    return {
        "success": True,
        "project_id": project_id,
        "report_id": generated["report_id"],
        "generated_at": report.get("generated_at"),
        "health_score": int(health.get("score", 0)),
        "health_status": health.get("status", "unknown"),
        "llm_used": bool(llm_status.get("used")),
        "report": report,
    }


@router.get("", response_model=ReportListResponse, summary="List persisted reports")
def list_project_reports(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    _require_project_member(project_id, current_user)
    try:
        reports = get_project_reports(project_id, limit=limit)
        total = count_project_reports(project_id)
    except ValueError as exc:
        raise _map_value_error(exc)
    return {
        "success": True,
        "project_id": project_id,
        "total_reports": total,
        "returned": len(reports),
        "reports": reports,
    }


@router.get("/latest", summary="Fetch the newest persisted report")
def get_latest_report(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_project_member(project_id, current_user)
    report = get_latest_project_report(project_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No reports have been generated for this project yet.",
        )
    return {"success": True, "project_id": project_id, "report": report}


# ---------------------------------------------------------------------------
# Schedule endpoints — declared BEFORE the dynamic /{report_id} route so
# FastAPI does not capture "schedules" as a report id.
# ---------------------------------------------------------------------------

@router.post("/schedules", summary="Create a report delivery schedule")
def create_schedule(
    project_id: str,
    payload: ReportScheduleCreate,
    current_user: dict = Depends(require_role(Role.ADMIN, Role.PROJECT_MANAGER)),
):
    _require_project_member(project_id, current_user)
    try:
        schedule_id = create_report_schedule(
            project_id,
            {
                "frequency": payload.frequency,
                "destinations": payload.destinations,
            },
        )
        schedule = get_schedule(schedule_id)
    except DatabaseError:
        raise
    except ValueError as exc:
        raise _map_value_error(exc)
    return {"success": True, "project_id": project_id, "schedules": [schedule]}


@router.get("/schedules", response_model=ScheduleListResponse, summary="List report schedules")
def list_schedules(
    project_id: str,
    status: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    _require_project_member(project_id, current_user)
    try:
        schedules = get_project_schedules(project_id, status=status)
    except ValueError as exc:
        raise _map_value_error(exc)
    return {"success": True, "project_id": project_id, "schedules": schedules}


@router.patch("/schedules/{schedule_id}", summary="Update a schedule")
def update_schedule(
    project_id: str,
    schedule_id: str,
    payload: ReportScheduleUpdate,
    current_user: dict = Depends(require_role(Role.ADMIN, Role.PROJECT_MANAGER)),
):
    _require_project_member(project_id, current_user)
    try:
        schedule = get_schedule(schedule_id)
        if not schedule or str(schedule.get("projectId")) != str(project_id):
            raise HTTPException(status_code=404, detail="Schedule not found for this project.")

        update_fields = payload.model_dump(exclude_none=True)
        if not update_fields:
            raise HTTPException(status_code=400, detail="No editable fields provided.")
        updated = update_report_schedule(schedule_id, update_fields)
        schedule = get_schedule(schedule_id)
    except DatabaseError:
        raise
    except ValueError as exc:
        raise _map_value_error(exc)
    return {
        "success": True,
        "project_id": project_id,
        "updated": bool(updated),
        "schedule": schedule,
    }


@router.delete("/schedules/{schedule_id}", response_model=SimpleSuccessResponse, summary="Delete a schedule")
def delete_schedule(
    project_id: str,
    schedule_id: str,
    current_user: dict = Depends(require_role(Role.ADMIN, Role.PROJECT_MANAGER)),
):
    _require_project_member(project_id, current_user)
    schedule = get_schedule(schedule_id)
    if not schedule or str(schedule.get("projectId")) != str(project_id):
        raise HTTPException(status_code=404, detail="Schedule not found for this project.")
    deleted = delete_report_schedule(schedule_id)
    return {
        "success": True,
        "detail": "Schedule deleted." if deleted else "Schedule was already deleted.",
    }


@router.post("/schedules/{schedule_id}/run", summary="Run a schedule now and stamp its lastRun")
def run_schedule(
    project_id: str,
    schedule_id: str,
    current_user: dict = Depends(
        require_role(Role.ADMIN, Role.PROJECT_MANAGER, Role.DEVELOPER)
    ),
):
    _require_project_member(project_id, current_user)
    schedule = get_schedule(schedule_id)
    if not schedule or str(schedule.get("projectId")) != str(project_id):
        raise HTTPException(status_code=404, detail="Schedule not found for this project.")
    if schedule.get("status") == "paused":
        raise HTTPException(status_code=400, detail="Schedule is paused; resume it before running.")

    try:
        generated = _generate_and_persist_report(project_id)
        record_schedule_run(schedule_id, status="completed", ran_at=datetime.now(timezone.utc))
    except DatabaseError:
        raise
    except ValueError as exc:
        raise _map_value_error(exc)

    report = generated["report"]
    health = report.get("project_health") or {}
    return {
        "success": True,
        "project_id": project_id,
        "schedule_id": schedule_id,
        "report_id": generated["report_id"],
        "generated_at": report.get("generated_at"),
        "health_score": int(health.get("score", 0)),
        "health_status": health.get("status", "unknown"),
        "report": report,
    }


# ---------------------------------------------------------------------------
# Single-report endpoints (dynamic segment last)
# ---------------------------------------------------------------------------

@router.get("/{report_id}", summary="Fetch one persisted report")
def get_single_report(
    project_id: str,
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_project_member(project_id, current_user)
    report = get_report(report_id)
    if not report or str(report.get("projectId")) != str(project_id):
        raise HTTPException(status_code=404, detail="Report not found for this project.")
    return {"success": True, "project_id": project_id, "report": report}


@router.delete("/{report_id}", response_model=SimpleSuccessResponse, summary="Delete one persisted report")
def delete_single_report(
    project_id: str,
    report_id: str,
    current_user: dict = Depends(require_role(Role.ADMIN, Role.PROJECT_MANAGER)),
):
    _require_project_member(project_id, current_user)
    report = get_report(report_id)
    if not report or str(report.get("projectId")) != str(project_id):
        raise HTTPException(status_code=404, detail="Report not found for this project.")
    deleted = delete_report(report_id)
    return {
        "success": True,
        "detail": "Report deleted." if deleted else "Report was already deleted.",
    }
