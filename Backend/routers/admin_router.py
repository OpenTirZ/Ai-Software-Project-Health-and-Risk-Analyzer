"""
Admin Router — mounts at /api/admin.

All endpoints require Role.ADMIN.

Endpoints:
    GET   /api/admin/users                      – List users (search, pagination, active-status)
    PATCH /api/admin/users/{id}/role            – Change a user's role
    POST  /api/admin/users/{id}/activate        – Activate a user account
    POST  /api/admin/users/{id}/deactivate      – Deactivate a user account
    GET   /api/admin/audit-logs                 – Fetch recent platform audit logs
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from Backend.auth.roles import Role, require_role
from Backend.persistence import (
    DatabaseError,
    create_audit_log,
    get_audit_logs,
    get_user,
    list_users_paginated,
    update_user,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)

# ---------------------------------------------------------------------------
# Pydantic schemas (admin-specific)
# ---------------------------------------------------------------------------

_VALID_ROLES = {r.value for r in Role}


class UserAdminOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: str


class PaginatedUsersResponse(BaseModel):
    items: list[UserAdminOut]
    total: int
    skip: int
    limit: int


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., description="New role: admin | project_manager | developer")


class AuditLogOut(BaseModel):
    id: str
    action: str
    actor_id: str
    target_id: Optional[str] = None
    detail: Optional[str] = None
    created_at: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_user_admin_out(doc: dict) -> UserAdminOut:
    return UserAdminOut(
        id=str(doc.get("_id", "")),
        name=doc.get("name", ""),
        email=doc.get("email", ""),
        role=doc.get("role", "developer"),
        is_active=doc.get("is_active", True),
        created_at=str(doc.get("createdAt", "")),
    )


def _write_audit_log(action: str, actor_id: str, target_id: str, detail: str) -> None:
    """Fire-and-forget audit record; never raises to callers."""
    try:
        create_audit_log(
            {
                "action": action,
                "actor_id": actor_id,
                "target_id": target_id,
                "detail": detail,
                "createdAt": datetime.now(timezone.utc),
            }
        )
    except Exception:  # pragma: no cover
        pass


def _get_actor_id(current_user: dict) -> str:
    return str(current_user.get("_id") or current_user.get("id") or "")


def _fetch_target_user(user_id: str) -> dict:
    """Retrieve target user or raise 404."""
    try:
        user = get_user(user_id)
    except (ValueError, DatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from exc
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=PaginatedUsersResponse,
    summary="List all platform users",
)
def list_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """
    Return a paginated list of all platform users.
    Supports full-text search over *name* and *email* fields
    and optional filtering by ``is_active``.
    """
    try:
        items, total = list_users_paginated(
            search=search,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return PaginatedUsersResponse(
        items=[_to_user_admin_out(u) for u in items],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{id}/role
# ---------------------------------------------------------------------------

@router.patch(
    "/users/{user_id}/role",
    response_model=UserAdminOut,
    summary="Update a user's platform role",
)
def update_user_role(
    user_id: str,
    payload: RoleUpdateRequest,
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """
    Change the role of an existing user.

    - Allowed values: ``admin``, ``project_manager``, ``developer``.
    - An admin **cannot** demote their own account.
    - A role-change audit record is created on success.
    """
    actor_id = _get_actor_id(current_user)

    # Validate requested role.
    new_role = payload.role.strip().lower()
    if new_role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{payload.role}'. Must be one of: {sorted(_VALID_ROLES)}.",
        )

    # Block self-demotion.
    target = _fetch_target_user(user_id)
    if str(target["_id"]) == actor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot change their own role.",
        )

    old_role = target.get("role", "developer")

    try:
        update_user(user_id, {"role": new_role, "updatedAt": datetime.now(timezone.utc)})
        updated = get_user(user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    _write_audit_log(
        action="role_change",
        actor_id=actor_id,
        target_id=user_id,
        detail=f"Role changed from '{old_role}' to '{new_role}'.",
    )

    return _to_user_admin_out(updated)


# ---------------------------------------------------------------------------
# POST /api/admin/users/{id}/activate
# ---------------------------------------------------------------------------

@router.post(
    "/users/{user_id}/activate",
    response_model=UserAdminOut,
    summary="Activate a user account",
)
def activate_user(
    user_id: str,
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """
    Re-activate a previously deactivated user.

    - An admin **cannot** activate/deactivate their own account
      (self-protection guard applies to both transitions).
    """
    actor_id = _get_actor_id(current_user)

    target = _fetch_target_user(user_id)
    if str(target["_id"]) == actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot modify their own account activation status.",
        )

    try:
        update_user(user_id, {"is_active": True, "updatedAt": datetime.now(timezone.utc)})
        updated = get_user(user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    _write_audit_log(
        action="user_activated",
        actor_id=actor_id,
        target_id=user_id,
        detail="Account activated.",
    )

    return _to_user_admin_out(updated)


# ---------------------------------------------------------------------------
# POST /api/admin/users/{id}/deactivate
# ---------------------------------------------------------------------------

@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserAdminOut,
    summary="Deactivate a user account",
)
def deactivate_user(
    user_id: str,
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """
    Deactivate a user account.

    - An admin **cannot** deactivate their own account.
    - Deactivated users receive **401 Unauthorized** on every subsequent
      authenticated request (enforced in ``get_current_user``).
    """
    actor_id = _get_actor_id(current_user)

    target = _fetch_target_user(user_id)
    if str(target["_id"]) == actor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot deactivate their own account.",
        )

    try:
        update_user(user_id, {"is_active": False, "updatedAt": datetime.now(timezone.utc)})
        updated = get_user(user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    _write_audit_log(
        action="user_deactivated",
        actor_id=actor_id,
        target_id=user_id,
        detail="Account deactivated.",
    )

    return _to_user_admin_out(updated)


# ---------------------------------------------------------------------------
# GET /api/admin/audit-logs
# ---------------------------------------------------------------------------

@router.get(
    "/audit-logs",
    response_model=list[AuditLogOut],
    summary="Fetch recent platform audit logs",
)
def fetch_audit_logs(
    limit: int = Query(100, ge=1, le=500, description="Max log entries to return"),
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """
    Return the most recent platform audit events, newest-first.
    """
    try:
        logs = get_audit_logs(limit=limit)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    result = []
    for log in logs:
        result.append(
            AuditLogOut(
                id=str(log.get("_id", "")),
                action=log.get("action", ""),
                actor_id=str(log.get("actor_id", "")),
                target_id=str(log.get("target_id")) if log.get("target_id") else None,
                detail=log.get("detail"),
                created_at=str(log.get("createdAt", "")),
            )
        )
    return result
