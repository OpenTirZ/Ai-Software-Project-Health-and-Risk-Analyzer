"""
Pydantic schemas for auth endpoints.
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from Backend.auth.normalization import normalize_email


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Full name of the user")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, v: str) -> str:
        if isinstance(v, str):
            return normalize_email(v)
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, v: str) -> str:
        if isinstance(v, str):
            return normalize_email(v)
        return v


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
