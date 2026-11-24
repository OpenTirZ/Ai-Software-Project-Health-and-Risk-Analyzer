"""Pydantic schemas for project health flag appeals."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AppealCreateRequest(BaseModel):
    flag_id: str = Field(..., min_length=1, max_length=120)
    reason: str = Field(..., min_length=10, max_length=2000)

    @field_validator("flag_id", "reason")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class AppealReviewRequest(BaseModel):
    # A reviewer may make a final decision only; pending is not a review action.
    status: Literal["approved", "rejected"]
    review_comment: str = Field(..., min_length=1, max_length=2000)

    @field_validator("review_comment")
    @classmethod
    def strip_review_comment(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A review comment is required.")
        return value


class AppealResponse(BaseModel):
    id: str
    project_id: str
    flag_id: str
    flag_type: str
    flag_message: str
    reason: str
    status: Literal["pending", "approved", "rejected"]
    submitted_by: str
    submitted_at: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None
