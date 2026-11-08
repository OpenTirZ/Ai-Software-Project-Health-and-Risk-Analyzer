"""
FastAPI router for Project Health & Risk Threshold Management.

Endpoints:
    GET /api/projects/{project_id}/thresholds – Retrieve project thresholds (with defaults)
    PUT /api/projects/{project_id}/thresholds – Update project thresholds (restricted to owner, admin, or lead)
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId, errors
from fastapi import APIRouter, Depends, HTTPException, status

from Backend.auth.dependencies import get_current_user
from Backend.auth.roles import Role, normalize_role
from Backend.persistence import DatabaseError, get_project, update_project
from Backend.routers.project_router import (
    _get_user_id,
    _is_project_member,
    _is_project_owner,
    _parse_object_id,
)
from Backend.schemas.threshold_schemas import (
    ThresholdConfig,
    ThresholdsResponse,
    UpdateThresholdsRequest,
)

router = APIRouter(prefix="/api/projects", tags=["Thresholds"])


# ---------------------------------------------------------------------------
# Authorization Helpers
# ---------------------------------------------------------------------------

def _is_user_authorized_for_threshold_update(project: dict, current_user: dict) -> bool:
    """
    Check if the user has permission to update thresholds.
    Allowed roles:
      - Global Role: admin
      - Global Role: lead / project_manager
      - Project-level Owner: creator (ownerId) or member with role 'owner' or 'lead'
    """
    user_id = _get_user_id(current_user)
    raw_role = current_user.get("role", "")
    normalized_sys_role = normalize_role(raw_role)

    # 1. Global Admin
    if normalized_sys_role == Role.ADMIN.value or raw_role.strip().lower() == "admin":
        return True

    # 2. Global Lead / Project Manager
    if (
        normalized_sys_role == Role.PROJECT_MANAGER.value
        or raw_role.strip().lower() in {"project_manager", "lead"}
    ):
        return True

    # 3. Project Owner (creator)
    if _is_project_owner(project, user_id):
        return True

    # 4. Project Member with designated owner or lead role
    members = project.get("members", [])
    if isinstance(members, list):
        for m in members:
            if isinstance(m, dict):
                member_user_id = m.get("userId") or m.get("user_id")
                member_role = str(m.get("role", "")).strip().lower()
                if (
                    member_user_id
                    and str(member_user_id) == str(user_id)
                    and member_role in {"owner", "lead", "project_manager", "admin"}
                ):
                    return True

    return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/thresholds",
    response_model=ThresholdsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve project health & risk thresholds",
)
def get_project_thresholds_endpoint(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve configured health and risk thresholds for a project.
    If the project has not configured custom thresholds, sensible system defaults
    are returned (e.g. stale PR > 48h, stale issue > 14 days, workload imbalance ratio > 3.0).
    Requires the caller to be a member or owner of the project (or global admin).
    """
    user_id = _get_user_id(current_user)
    oid = _parse_object_id(project_id)

    try:
        project = get_project(str(oid))
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    user_role = current_user.get("role", "").strip().lower()
    is_admin = user_role in {Role.ADMIN.value, "admin"}

    if not is_admin and not _is_project_member(project, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this project.",
        )

    saved_thresholds = project.get("thresholds")
    if saved_thresholds and isinstance(saved_thresholds, dict):
        # Merge with defaults in case new threshold fields were added
        merged_config = ThresholdConfig(**{**ThresholdConfig().model_dump(), **saved_thresholds})
        return ThresholdsResponse(
            project_id=str(oid),
            thresholds=merged_config,
            is_customized=True,
            updated_at=project.get("thresholds_updated_at") or project.get("updatedAt"),
        )

    # Return system defaults
    return ThresholdsResponse(
        project_id=str(oid),
        thresholds=ThresholdConfig(),
        is_customized=False,
        updated_at=None,
    )


@router.put(
    "/{project_id}/thresholds",
    response_model=ThresholdsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project health & risk thresholds",
)
def update_project_thresholds_endpoint(
    project_id: str,
    payload: UpdateThresholdsRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update project health & risk thresholds.
    Restricted to project owner, admin, or lead.
    Validates input bounds and returns clear error messages on invalid values.
    """
    oid = _parse_object_id(project_id)

    try:
        project = get_project(str(oid))
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if not _is_user_authorized_for_threshold_update(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only project owners, admins, or leads can update thresholds.",
        )

    # Fetch existing thresholds or defaults to support partial updates
    current_thresholds = project.get("thresholds")
    if not current_thresholds or not isinstance(current_thresholds, dict):
        base_thresholds = ThresholdConfig().model_dump()
    else:
        base_thresholds = {**ThresholdConfig().model_dump(), **current_thresholds}

    update_dict = payload.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if value is not None:
            base_thresholds[key] = value

    # Validate resulting config through ThresholdConfig
    validated_config = ThresholdConfig(**base_thresholds)

    now = datetime.now(timezone.utc)
    update_data = {
        "thresholds": validated_config.model_dump(),
        "thresholds_updated_at": now,
        "updatedAt": now,
    }

    try:
        update_project(str(oid), update_data)
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return ThresholdsResponse(
        project_id=str(oid),
        thresholds=validated_config,
        is_customized=True,
        updated_at=now,
    )
