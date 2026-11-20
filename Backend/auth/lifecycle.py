"""
User Lifecycle Management API — AI Software Project Health & Risk Analyzer
-------------------------------------------------------------------------
Handles administrative user lifecycle operations:
  - Account Deactivation: POST /api/users/{id}/deactivate (Admin only)
"""

from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from Backend.auth.roles import Role, require_role
from Backend.persistence import DatabaseError, get_user, update_user

router = APIRouter(tags=["User Lifecycle"])


class DeactivateResponse(BaseModel):
    message: str = Field(..., description="Status confirmation message")
    user_id: str = Field(..., description="ID of the deactivated user account")
    is_active: bool = Field(default=False, description="Whether the account is active")


@router.post(
    "/api/users/{id}/deactivate",
    response_model=DeactivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate a user account (Admin only)",
)
@router.post(
    "/users/{id}/deactivate",
    response_model=DeactivateResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def deactivate_user(
    id: str = Path(..., description="The ID of the user to deactivate"),
    admin_user: dict = Depends(require_role(Role.ADMIN)),
):
    """
    Deactivates a user account.
    Restricted to system administrators.
    Sets is_active: false in the user document, immediately invalidating any active JWT sessions.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format.",
        )

    try:
        user = get_user(id)
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    now = datetime.now(timezone.utc)
    try:
        update_user(id, {"is_active": False, "updatedAt": now})
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return DeactivateResponse(
        message="User account deactivated successfully.",
        user_id=id,
        is_active=False,
    )
