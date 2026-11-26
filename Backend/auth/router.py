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
from Backend.auth.otp import generate_otp, save_otp, send_otp_email, verify_otp
from Backend.auth.schemas import (
    LoginRequest,
    MessageResponse,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    OTPRequest,
    OTPResponse,
    OTPVerifyRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from Backend.auth.security import create_access_token, hash_password, verify_password
from Backend.persistence import create_user, get_user, get_user_by_email, update_user, DatabaseError

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
    try:
        existing = get_user_by_email(payload.email)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

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
        "role": "developer",
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        user_id = create_user(user_doc)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    access_token = create_access_token({"sub": user_id, "role": user_doc["role"]})
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

    try:
        user = get_user_by_email(payload.email)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not user:
        raise invalid_exc

    if (
        not verify_password(payload.password, user.get("password_hash", ""))
        or user.get("is_active") is False
    ):
        raise invalid_exc

    access_token = create_access_token({"sub": user["_id"], "role": user.get("role", "developer")})

    return TokenResponse(
        access_token=access_token,
        user=_build_user_out(user),
    )


# ---------------------------------------------------------------------------
# POST /auth/request-otp
# ---------------------------------------------------------------------------

@router.post(
    "/request-otp",
    response_model=OTPResponse,
    summary="Request a one-time password (OTP) via email",
)
def request_otp(payload: OTPRequest):
    """
    Generate and dispatch a 6-digit numeric OTP to the user's email address.

    - Verifies the user exists and is active.
    - Generates a cryptographically random 6-digit code.
    - Stores salted SHA-256 hash with 5-minute TTL in database.
    - Sends the OTP code to the user via SMTP email.
    """
    try:
        user = get_user_by_email(payload.email)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address.",
        )

    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    code = generate_otp()
    try:
        save_otp(payload.email, code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to process OTP request: {exc}",
        )

    send_otp_email(payload.email, code)

    return OTPResponse(
        message="OTP sent successfully to your email.",
        email=payload.email,
    )


# ---------------------------------------------------------------------------
# POST /auth/verify-otp
# ---------------------------------------------------------------------------

@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    summary="Verify an OTP code and receive a JWT token",
)
def verify_otp_endpoint(payload: OTPVerifyRequest):
    """
    Validate an OTP code sent via email.

    - Verifies user exists and is active.
    - Validates matching OTP code, 5-minute TTL, and max 3 attempts limit.
    - Immediately consumes / invalidates the OTP upon successful verification.
    - Issues a standard JWT access token on success.
    """
    try:
        user = get_user_by_email(payload.email)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address.",
        )

    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    try:
        valid, err_msg = verify_otp(payload.email, payload.code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to verify OTP: {exc}",
        )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    access_token = create_access_token(
        {"sub": user["_id"], "role": user.get("role", "developer")}
    )

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


# ---------------------------------------------------------------------------
# Notification preferences: GET & PATCH /auth/me/settings
# ---------------------------------------------------------------------------

@router.get(
    "/me/settings",
    response_model=NotificationPreferences,
    summary="Get the authenticated user's notification preferences",
)
def get_settings(current_user: dict = Depends(get_current_user)):
    """
    Returns the current user's notification preferences.
    If preferences have not been explicitly saved yet, returns default preferences.
    """
    raw_prefs = current_user.get("notification_preferences")
    if not isinstance(raw_prefs, dict):
        return NotificationPreferences()
    return NotificationPreferences(**raw_prefs)


@router.patch(
    "/me/settings",
    response_model=NotificationPreferences,
    summary="Update the authenticated user's notification preferences",
)
def update_settings(
    payload: NotificationPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Partially or fully update notification preferences.
    Preserves existing preference values when omitted in the request.
    Validates extra fields via extra='forbid'.
    """
    user_id = str(current_user["_id"])
    existing_raw = current_user.get("notification_preferences")
    existing_prefs = existing_raw if isinstance(existing_raw, dict) else {}

    # Defaults baseline
    merged = {
        "high_risk_threshold": existing_prefs.get("high_risk_threshold", True),
        "weekly_digest": existing_prefs.get("weekly_digest", True),
    }

    # Apply provided partial updates
    update_data = payload.model_dump(exclude_unset=True)
    merged.update(update_data)

    try:
        update_user(user_id, {"notification_preferences": merged})
        fresh_user = get_user(user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    stored_raw = (fresh_user or {}).get("notification_preferences", merged)
    return NotificationPreferences(**stored_raw)
