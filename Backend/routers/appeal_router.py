"""Endpoints for developer appeals against generated project health flags."""

from datetime import datetime, timezone
import logging

from bson import ObjectId, errors
from fastapi import APIRouter, Depends, HTTPException, Path, status

from Backend.auth.dependencies import get_current_user
from Backend.auth.roles import Role, normalize_role
from Backend.persistence import (
    create_appeal,
    get_appeal,
    get_project,
    get_project_appeals,
    update_appeal,
)
from Backend.routers.metric_router import _fetch_project_data
from Backend.analysis.health_summary import build_health_summary
from Backend.schemas.appeal_schemas import (
    AppealCreateRequest,
    AppealReviewRequest,
    AppealResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Project Appeals"])


def _validate_object_id(value: str, label: str) -> str:
    try:
        ObjectId(value)
        return value
    except (errors.InvalidId, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label} ID format.",
        )


def _get_user_id(user: dict) -> str:
    user_id = user.get("_id") or user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )
    return str(user_id)


def _is_project_member(project: dict, user_id: str) -> bool:
    """Return True for the project owner or an explicitly listed member."""
    owner_id = project.get("ownerId") or project.get("owner_id")
    if owner_id is not None and str(owner_id) == user_id:
        return True

    members = project.get("members", [])
    if not isinstance(members, list):
        return False

    for member in members:
        if isinstance(member, dict):
            member_id = member.get("userId") or member.get("user_id")
        else:
            member_id = member
        if member_id is not None and str(member_id) == user_id:
            return True
    return False


def _load_project(project_id: str) -> dict:
    project_id = _validate_object_id(project_id, "project")
    project = get_project(project_id)
    if (
        not project
        or project.get("status") in {"deleted", "archived"}
        or project.get("is_active") is False
        or project.get("deletion_status") in {"pending", "completed"}
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


def _require_project_membership(project: dict, user: dict) -> str:
    user_id = _get_user_id(user)
    if not _is_project_member(project, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this project.",
        )
    return user_id


def _serialize_appeal(document: dict) -> dict:
    if not document:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve the appeal.",
        )
    return {
        "id": str(document.get("_id") or document.get("id")),
        "project_id": str(document["projectId"]),
        "flag_id": document["flagId"],
        "flag_type": document["flagType"],
        "flag_message": document["flagMessage"],
        "reason": document["reason"],
        "status": document["status"],
        "submitted_by": str(document["submittedBy"]),
        "submitted_at": document["submittedAt"],
        "reviewed_by": str(document["reviewedBy"]) if document.get("reviewedBy") else None,
        "reviewed_at": document.get("reviewedAt"),
        "review_comment": document.get("reviewComment"),
    }


@router.post(
    "/{project_id}/appeals",
    response_model=AppealResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an appeal against a health flag",
)
def submit_appeal(
    payload: AppealCreateRequest,
    project_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
):
    """Allow a project developer to appeal a currently generated health flag."""
    if normalize_role(current_user.get("role")) != Role.DEVELOPER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can submit appeals.",
        )

    project_id = _validate_object_id(project_id, "project")
    project = _load_project(project_id)
    user_id = _require_project_membership(project, current_user)

    # Reuse the existing health analysis so clients cannot appeal arbitrary IDs.
    data = _fetch_project_data(project_id, current_user)
    summary = build_health_summary(
        project=data[0],
        commits=data[1],
        contributors=data[2],
        pull_requests=data[3],
        issues=data[4],
        sprints=data[5],
    )
    flag = next(
        (item for item in summary.get("active_flags", []) if item.get("id") == payload.flag_id),
        None,
    )
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified active health flag was not found.",
        )

    appeal_data = {
        "projectId": ObjectId(project_id),
        "flagId": flag["id"],
        "flagType": flag.get("type", "unknown"),
        "flagMessage": flag.get("message", ""),
        "reason": payload.reason,
        "status": "pending",
        "submittedBy": user_id,
        "submittedAt": datetime.now(timezone.utc).isoformat(),
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewComment": None,
    }
    appeal_id = create_appeal(appeal_data)
    return _serialize_appeal(get_appeal(appeal_id))


@router.get(
    "/{project_id}/appeals",
    response_model=list[AppealResponse],
    summary="List project appeals",
)
def list_appeals(
    project_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
):
    """Developers see their own appeals; project managers see all project appeals."""
    project_id = _validate_object_id(project_id, "project")
    project = _load_project(project_id)
    role = normalize_role(current_user.get("role"))

    if role not in {Role.DEVELOPER.value, Role.PROJECT_MANAGER.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view appeals.",
        )

    user_id = _require_project_membership(project, current_user)
    appeals = get_project_appeals(project_id)
    if role == Role.DEVELOPER.value:
        appeals = [item for item in appeals if str(item.get("submittedBy")) == user_id]

    return [_serialize_appeal(item) for item in appeals]


@router.patch(
    "/{project_id}/appeals/{appeal_id}",
    response_model=AppealResponse,
    summary="Approve or reject an appeal",
)
def review_appeal(
    payload: AppealReviewRequest,
    project_id: str = Path(...),
    appeal_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
):
    """Allow a project manager (team lead) who belongs to the project to review."""
    if normalize_role(current_user.get("role")) != Role.PROJECT_MANAGER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project managers (team leads) can review appeals.",
        )

    project_id = _validate_object_id(project_id, "project")
    appeal_id = _validate_object_id(appeal_id, "appeal")
    project = _load_project(project_id)
    reviewer_id = _require_project_membership(project, current_user)

    appeal = get_appeal(appeal_id)
    if not appeal or str(appeal.get("projectId")) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appeal not found.",
        )
    if appeal.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appeal has already been reviewed.",
        )

    updated = update_appeal(
        appeal_id,
        {
            "status": payload.status,
            "reviewedBy": reviewer_id,
            "reviewedAt": datetime.now(timezone.utc).isoformat(),
            "reviewComment": payload.review_comment,
        },
        expected_status="pending",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appeal has already been reviewed.",
        )

    return _serialize_appeal(get_appeal(appeal_id))
