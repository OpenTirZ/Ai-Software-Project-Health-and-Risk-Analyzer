"""
FastAPI router for Project Management and Repository Association.
Endpoints:
    POST  /api/projects               – Create project (owner association)
    GET   /api/projects               – List authenticated user's projects
    GET   /api/projects/{project_id}  – Retrieve project by ID (membership required)
    PATCH /api/projects/{project_id}  – Update project configuration (owner only)
"""
from datetime import datetime, timezone
from typing import List

from bson import ObjectId, errors
from fastapi import APIRouter, Depends, HTTPException, status

from Backend.auth.dependencies import get_current_user
from Backend.persistence import (
    create_project,
    get_project,
    get_projects_by_user,
    update_project,
)
from Backend.schemas.project_schemas import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _parse_object_id(id_str: str) -> ObjectId:
    """Validate and convert string to BSON ObjectId; raise 400 if invalid."""
    try:
        return ObjectId(id_str)
    except (errors.InvalidId, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format.",
        )


def _get_user_id(current_user: dict) -> str:
    """Extract string user ID from authenticated user document."""
    user_id = current_user.get("_id") or current_user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )
    return str(user_id)


def _is_project_owner(project: dict, user_id: str) -> bool:
    """Check if the user is the recorded owner of the project."""
    owner_val = project.get("ownerId") or project.get("owner_id")
    if not owner_val:
        return False
    return str(owner_val) == str(user_id)


def _is_project_member(project: dict, user_id: str) -> bool:
    """Check if the user is an owner or recorded member of the project."""
    if _is_project_owner(project, user_id):
        return True

    members = project.get("members", [])
    if not isinstance(members, list):
        return False

    for m in members:
        if isinstance(m, dict):
            member_user_id = m.get("userId") or m.get("user_id")
            if member_user_id and str(member_user_id) == str(user_id):
                return True
    return False


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
def create_project_endpoint(
    payload: CreateProjectRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new project. The authenticated caller becomes the project owner
    and initial member.
    """
    user_id = _get_user_id(current_user)
    owner_oid = ObjectId(user_id)
    now = datetime.now(timezone.utc)

    project_data = {
        "name": payload.name,
        "description": payload.description,
        "ownerId": owner_oid,
        "repo_url": payload.repo_url,
        "default_branch": payload.default_branch or "main",
        "members": [
            {"userId": owner_oid, "role": "owner"}
        ],
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    }

    inserted_id = create_project(project_data)
    created_doc = get_project(inserted_id)
    if not created_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created project.",
        )

    return ProjectResponse.from_doc(created_doc)


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List authenticated user's projects",
)
def list_projects_endpoint(
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve all projects where the authenticated user is an owner or member.
    Unowned legacy projects without verified ownership or membership are excluded.
    """
    user_id = _get_user_id(current_user)
    projects = get_projects_by_user(user_id)

    # Strictly enforce verified ownership or membership
    user_projects = [
        ProjectResponse.from_doc(p)
        for p in projects
        if _is_project_member(p, user_id)
    ]
    return user_projects


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
)
def get_project_endpoint(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve a specific project by its ID.
    The caller must be a verified owner or member.
    """
    user_id = _get_user_id(current_user)
    oid = _parse_object_id(project_id)

    project = get_project(str(oid))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if not _is_project_member(project, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this project.",
        )

    return ProjectResponse.from_doc(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project configuration",
)
def update_project_endpoint(
    project_id: str,
    payload: UpdateProjectRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update project details and configuration (name, description, repo_url, default_branch).
    Only the verified project owner can update project configuration.
    """
    user_id = _get_user_id(current_user)
    oid = _parse_object_id(project_id)

    project = get_project(str(oid))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if not _is_project_owner(project, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can update project configuration.",
        )

    update_fields = {}
    if payload.name is not None:
        update_fields["name"] = payload.name
    if payload.description is not None:
        update_fields["description"] = payload.description
    if payload.repo_url is not None:
        update_fields["repo_url"] = payload.repo_url
    if payload.default_branch is not None:
        update_fields["default_branch"] = payload.default_branch

    update_fields["updatedAt"] = datetime.now(timezone.utc)

    update_project(str(oid), update_fields)
    updated_doc = get_project(str(oid))
    if not updated_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated project.",
        )

    return ProjectResponse.from_doc(updated_doc)
