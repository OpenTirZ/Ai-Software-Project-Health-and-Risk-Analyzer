"""
Auth router — mounts at /auth.

Endpoints:
    POST /auth/signup  – Register a new user
    POST /auth/login   – Obtain a JWT token
    POST /auth/logout  – Stateless logout (client discards token)
    GET  /auth/me      – Return the authenticated user's profile
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from Backend.auth.dependencies import get_current_user
from Backend.auth.schemas import (
    LoginRequest,
    MessageResponse,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from Backend.auth.security import create_access_token, hash_password, verify_password
from Backend.persistence import create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["_id"],
        name=user["name"],
        email=user["email"],
        role=user.get("role", "member"),
        created_at=user.get("createdAt", ""),
    )


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def signup(payload: SignupRequest):
    """
    Create a new user account.

    - **name**: Full name of the user
    - **email**: Must be unique
    - **password**: Plain-text (hashed before storage; never stored in plain text)
    """
    # Reject duplicate emails
    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "name": payload.name,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": "member",
        "createdAt": now,
        "updatedAt": now,
    }

    user_id = create_user(user_doc)

    access_token = create_access_token({"sub": user_id})
    user_doc["_id"] = user_id  # add id for the response

    return TokenResponse(
        access_token=access_token,
        user=_build_user_out(user_doc),
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in and receive a JWT token",
)
def login(payload: LoginRequest):
    """
    Authenticate with email + password.

    Returns a Bearer token on success.
    Returns **401** for invalid credentials (intentionally vague to prevent
    user enumeration).
    """
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = get_user_by_email(payload.email)
    if not user:
        raise invalid_exc

    if not verify_password(payload.password, user.get("password_hash", "")):
        raise invalid_exc

    access_token = create_access_token({"sub": user["_id"]})

    return TokenResponse(
        access_token=access_token,
        user=_build_user_out(user),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Sign out (stateless)",
)
def logout(_: dict = Depends(get_current_user)):
    """
    Stateless logout — the client must discard the token.

    For token revocation, a server-side denylist (e.g. Redis) can be added
    later without changing this interface.
    """
    return MessageResponse(message="Logged out successfully.")


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the current user's profile",
)
def me(current_user: dict = Depends(get_current_user)):
    """
    Returns the authenticated user's profile.

    Requires: `Authorization: Bearer <token>` header.
    """
    return _build_user_out(current_user)
