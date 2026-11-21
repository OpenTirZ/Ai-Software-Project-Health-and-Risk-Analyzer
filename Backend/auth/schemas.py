"""
Pydantic schemas for auth endpoints.
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Full name of the user")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Notification preferences schemas
# ---------------------------------------------------------------------------

class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_risk_threshold: bool = True
    weekly_digest: bool = True


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_risk_threshold: bool | None = None
    weekly_digest: bool | None = None
