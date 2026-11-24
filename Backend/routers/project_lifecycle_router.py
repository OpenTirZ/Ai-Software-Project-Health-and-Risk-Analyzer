"""
Project Lifecycle Management Router — AI Software Project Health & Risk Analyzer
---------------------------------------------------------------------------------
Task: TASK-SP4-07 (Issue #114)

Handles administrative and ownership project lifecycle operations:
  - Archive Project: POST /api/projects/{id}/archive
  - Soft-Delete Project: DELETE /api/projects/{id}
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from Backend.auth.dependencies import get_current_user
from Backend.auth.roles import Role, normalize_role
from Backend.database import (
    commits_collection,
    contributors_collection,
    flags_collection,
    integration_credentials_collection,
    issues_collection,
    metric_snapshots_collection,
    milestones_collection,
    pull_requests_collection,
    report_schedules_collection,
    reports_collection,
    sprints_collection,
)
from Backend.persistence import (
    DatabaseError,
    archive_project_conditional,
    get_project,
    soft_delete_cascade_collection,
    soft_delete_complete,
    soft_delete_initiate_conditional,
)
from Backend.routers.project_router import (
    _get_user_id,
    _is_project_owner,
    _parse_object_id,
)

router = APIRouter(prefix="/api/projects", tags=["Project Lifecycle"])


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class ArchiveProjectResponse(BaseModel):
    message: str = Field(..., description="Confirmation message")
    project_id: str = Field(..., description="ID of the archived project")
    status: str = Field("archived", description="Project lifecycle status")
    archived_at: Optional[str] = Field(None, description="ISO timestamp of archival")


class DeleteProjectResponse(BaseModel):
    message: str = Field(..., description="Confirmation message")
    project_id: str = Field(..., description="ID of the soft-deleted project")
    status: str = Field("deleted", description="Project lifecycle status")
    is_active: bool = Field(False, description="Whether the project is active")
    deletion_status: str = Field("completed", description="Cascade completion status")
    deleted_at: Optional[str] = Field(None, description="ISO timestamp of soft deletion")
    cascade_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of cascaded collections")


# ---------------------------------------------------------------------------
# Authorization Helper
# ---------------------------------------------------------------------------

def _require_owner_or_admin(project: dict, current_user: dict) -> None:
    """
    Ensure the authenticated caller is the project owner or a system administrator.
    Normal members and outsiders are rejected with HTTP 403 Forbidden.
    """
    user_id = _get_user_id(current_user)
    raw_role = current_user.get("role")
    normalized_sys_role = normalize_role(raw_role)

    is_admin = (
        normalized_sys_role == Role.ADMIN.value
        or (isinstance(raw_role, str) and raw_role.strip().lower() == "admin")
    )
    is_owner = _is_project_owner(project, user_id)

    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this lifecycle action. Only the project owner or an administrator can archive or delete a project.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{id}/archive",
    response_model=ArchiveProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a project (Owner or Admin only)",
)
def archive_project_endpoint(
    id: str = Path(..., description="ID of the project to archive"),
    current_user: dict = Depends(get_current_user),
):
    """
    Mark a project as archived.
    An archived project becomes strictly read-only: data synchronization and configuration
    mutations are disabled, while existing data and historical telemetry remain readable.
    """
    oid = _parse_object_id(id)

    # 1. Fetch project for authorization verification
    try:
        project = get_project(str(oid))
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    _require_owner_or_admin(project, current_user)

    now = datetime.now(timezone.utc)
    try:
        outcome, updated_project = archive_project_conditional(str(oid), now=now)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if outcome == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if outcome == "invalid_state_deleted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot archive a project that is deleted or pending deletion.",
        )

    if outcome == "already_archived":
        return ArchiveProjectResponse(
            message="Project is already archived.",
            project_id=str(oid),
            status="archived",
            archived_at=str(updated_project.get("archivedAt") or ""),
        )

    if outcome == "archived_success":
        return ArchiveProjectResponse(
            message="Project archived successfully.",
            project_id=str(oid),
            status="archived",
            archived_at=str(updated_project.get("archivedAt") or now.isoformat()),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Project cannot be archived in its current lifecycle state.",
    )


@router.delete(
    "/{id}",
    response_model=DeleteProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a project (Owner or Admin only)",
)
def delete_project_endpoint(
    id: str = Path(..., description="ID of the project to soft-delete"),
    current_user: dict = Depends(get_current_user),
):
    """
    Soft-delete a project and cascade inactive status across all associated collections.
    Does not physically delete project or telemetry documents, preserving historical audit trails.
    """
    oid = _parse_object_id(id)

    try:
        project = get_project(str(oid))
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    _require_owner_or_admin(project, current_user)

    now = datetime.now(timezone.utc)
    try:
        outcome, canonical_deleted_at, updated_project = soft_delete_initiate_conditional(str(oid), now=now)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if outcome == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if outcome == "already_completed":
        return DeleteProjectResponse(
            message="Project is already deleted.",
            project_id=str(oid),
            status="deleted",
            is_active=False,
            deletion_status="completed",
            deleted_at=str(canonical_deleted_at),
            cascade_summary={"collections_cascaded": 11, "resumed": False},
        )

    # Execute cascade across all 11 project-associated collections
    cascade_targets = [
        (commits_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (pull_requests_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (issues_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (milestones_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (sprints_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (flags_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (reports_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (contributors_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (metric_snapshots_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
        (report_schedules_collection, {"enabled": False, "status": "paused", "is_active": False, "deletedAt": canonical_deleted_at}),
        (integration_credentials_collection, {"is_active": False, "deletedAt": canonical_deleted_at}),
    ]

    try:
        for collection, update_fields in cascade_targets:
            soft_delete_cascade_collection(str(oid), collection, update_fields)
        soft_delete_complete(str(oid))
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return DeleteProjectResponse(
        message="Project soft-deleted successfully.",
        project_id=str(oid),
        status="deleted",
        is_active=False,
        deletion_status="completed",
        deleted_at=str(canonical_deleted_at),
        cascade_summary={"collections_cascaded": 11, "resumed": outcome == "resuming_pending"},
    )
