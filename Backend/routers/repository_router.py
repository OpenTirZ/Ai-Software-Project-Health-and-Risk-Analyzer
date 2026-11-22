"""
FastAPI router for GitHub Repository Association and Branch Discovery.
------------------------------------------------------------------------
Provides endpoints compatible with Frontend repository services:
    POST /api/repositories/connect   – Connect GitHub repository to an existing project
    GET  /api/repositories           – List all connected repositories for user's projects
    GET  /api/repositories/branches  – Discover branches for a GitHub repository URL
"""

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bson import ObjectId, errors
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from Backend.auth.dependencies import get_current_user
from Backend.persistence import DatabaseError, get_project, get_projects_by_user, update_project
from Backend.routers.project_router import _get_user_id, _is_project_owner, _parse_object_id

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConnectRepositoryRequest(BaseModel):
    projectId: str = Field(..., description="Project ObjectId")
    githubUrl: str = Field(..., description="Target GitHub repository URL")
    branch: Optional[str] = Field("main", description="Target Git branch name")


class RepositoryItemResponse(BaseModel):
    id: str
    projectId: str
    repoName: str
    githubUrl: str
    branch: str
    connectedAt: str
    status: str = "connected"


class BranchListResponse(BaseModel):
    branches: List[str]
    source: str  # "github" or "default"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_repo_slug(github_url: str) -> tuple[str, str]:
    """Extract (owner, repo_name) from standard GitHub URLs."""
    clean_url = github_url.strip().rstrip("/")
    match = re.match(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", clean_url)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub repository URL format. Must be https://github.com/owner/repository",
        )
    return match.group(1), match.group(2)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/connect",
    response_model=RepositoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a GitHub repository to a project",
)
def connect_repository_endpoint(
    payload: ConnectRepositoryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Connect a GitHub repository to a project by updating its repo_url and default_branch.
    Only the project owner or admin can connect a repository.
    """
    user_id = _get_user_id(current_user)
    oid = _parse_object_id(payload.projectId)
    owner, repo_slug = _extract_repo_slug(payload.githubUrl)

    try:
        project = get_project(str(oid))
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if (
        not project
        or project.get("status") == "deleted"
        or project.get("is_active") is False
        or project.get("deletion_status") in ("pending", "completed")
    ):
        raise HTTPException(status_code=404, detail="Project not found.")

    if project.get("status") == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is archived and read-only. Cannot connect repository.",
        )

    is_admin = current_user.get("role", "").strip().lower() == "admin"
    if not is_admin and not _is_project_owner(project, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the project owner or an admin can connect a repository.",
        )

    clean_url = payload.githubUrl.strip().rstrip("/")
    target_branch = (payload.branch or "main").strip()
    now = datetime.now(timezone.utc)

    update_data = {
        "repo_url": clean_url,
        "default_branch": target_branch,
        "updatedAt": now,
        "lastSyncedAt": now,
    }

    try:
        update_project(str(oid), update_data)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return RepositoryItemResponse(
        id=f"repo_{str(oid)}",
        projectId=str(oid),
        repoName=repo_slug,
        githubUrl=clean_url,
        branch=target_branch,
        connectedAt=now.isoformat(),
        status="connected",
    )


@router.get(
    "",
    response_model=List[RepositoryItemResponse],
    summary="List all connected repositories for current user's projects",
)
def list_repositories_endpoint(
    current_user: dict = Depends(get_current_user),
):
    """
    List all projects that have a connected repository accessible by the current user.
    """
    user_id = _get_user_id(current_user)
    try:
        projects = get_projects_by_user(user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    results: List[RepositoryItemResponse] = []
    for p in projects:
        if (
            p.get("status") == "deleted"
            or p.get("is_active") is False
            or p.get("deletion_status") in ("pending", "completed")
        ):
            continue

        repo_url = p.get("repo_url")
        if not repo_url:
            continue

        match = re.search(r"github\.com/[^/]+/([^/]+)", repo_url)
        slug = match.group(1).replace(".git", "") if match else p.get("name", "repository")
        pid = str(p.get("_id") or p.get("id"))
        connected_at = str(p.get("lastSyncedAt") or p.get("updatedAt") or p.get("createdAt") or "")

        results.append(
            RepositoryItemResponse(
                id=f"repo_{pid}",
                projectId=pid,
                repoName=slug,
                githubUrl=repo_url,
                branch=p.get("default_branch") or "main",
                connectedAt=connected_at,
                status="connected",
            )
        )

    return results


@router.get(
    "/branches",
    response_model=BranchListResponse,
    summary="Fetch remote branches for a GitHub repository",
)
def fetch_branches_endpoint(
    url: Optional[str] = Query(None, description="GitHub repository URL"),
    current_user: dict = Depends(get_current_user),
):
    """
    Query GitHub API from the backend server to discover active branches.
    Uses GITHUB_TOKEN if configured in server environment to avoid rate limits.
    """
    default_branches = ["main", "master", "develop", "staging", "production"]
    if not url:
        return BranchListResponse(branches=default_branches, source="default")

    clean_url = url.strip().rstrip("/")
    match = re.match(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", clean_url)
    if not match:
        return BranchListResponse(branches=default_branches, source="default")

    owner, repo = match.group(1), match.group(2)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_API_TOKEN")

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Ai-Software-Project-Health-Analyzer",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches",
            headers=headers,
            params={"per_page": 50},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                branch_names = [b.get("name") for b in data if isinstance(b, dict) and b.get("name")]
                if branch_names:
                    return BranchListResponse(branches=branch_names, source="github")
    except Exception:
        pass

    return BranchListResponse(branches=default_branches, source="default")

