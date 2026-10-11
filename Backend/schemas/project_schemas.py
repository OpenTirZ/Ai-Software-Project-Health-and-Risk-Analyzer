"""
Pydantic schemas for Project Management and Repository Association.
"""
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# Regular expression to validate standard GitHub repository URLs
# Allows https://github.com/{owner}/{repo} with optional .git suffix and optional trailing slash
GITHUB_REPO_URL_REGEX = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$"
)

# Regular expression to validate Git branch names (common alphanumeric and standard branch characters)
BRANCH_NAME_REGEX = re.compile(r"^[A-Za-z0-9_.\-\/]+$")


class ProjectMember(BaseModel):
    userId: str = Field(..., description="User ID of the project member")
    role: str = Field("member", description="Role of the member (e.g., 'owner', 'member')")


class CreateProjectRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the project (1–200 characters)",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Optional project description (up to 2000 characters)",
    )
    repo_url: Optional[str] = Field(
        None,
        description="Associated GitHub repository URL (e.g. https://github.com/owner/repo)",
    )
    default_branch: Optional[str] = Field(
        "main",
        min_length=1,
        max_length=100,
        description="Default git branch for analysis (defaults to 'main')",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty or whitespace only.")
        return stripped

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if not GITHUB_REPO_URL_REGEX.match(stripped):
            raise ValueError(
                "Invalid repository URL. Must be a valid GitHub repository URL "
                "(e.g., https://github.com/owner/repository)."
            )
        return stripped.rstrip("/")

    @field_validator("default_branch")
    @classmethod
    def validate_default_branch(cls, v: Optional[str]) -> str:
        if v is None:
            return "main"
        stripped = v.strip()
        if not stripped:
            raise ValueError("Default branch cannot be empty or whitespace only.")
        if not BRANCH_NAME_REGEX.match(stripped):
            raise ValueError("Invalid branch name format.")
        return stripped


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated project name (1–200 characters)",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Updated project description",
    )
    repo_url: Optional[str] = Field(
        None,
        description="Updated associated GitHub repository URL",
    )
    default_branch: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Updated default git branch",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty or whitespace only.")
        return stripped

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if not GITHUB_REPO_URL_REGEX.match(stripped):
            raise ValueError(
                "Invalid repository URL. Must be a valid GitHub repository URL "
                "(e.g., https://github.com/owner/repository)."
            )
        return stripped.rstrip("/")

    @field_validator("default_branch")
    @classmethod
    def validate_default_branch(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Default branch cannot be empty or whitespace only.")
        if not BRANCH_NAME_REGEX.match(stripped):
            raise ValueError("Invalid branch name format.")
        return stripped


class ProjectResponse(BaseModel):
    id: str = Field(..., description="Project document ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    ownerId: str = Field(..., description="Owner user ID")
    repo_url: Optional[str] = Field(None, description="Associated GitHub repository URL")
    default_branch: str = Field("main", description="Default git branch")
    members: List[ProjectMember] = Field(default_factory=list, description="Project members")
    status: str = Field("active", description="Project status")
    createdAt: Optional[str] = Field(None, description="ISO timestamp of creation")
    updatedAt: Optional[str] = Field(None, description="ISO timestamp of last update")

    @classmethod
    def from_doc(cls, doc: dict) -> "ProjectResponse":
        """Build a ProjectResponse from a serialized MongoDB document."""
        # Handle field mappings for id / _id, ownerId / owner_id, timestamps
        members_data = []
        for m in doc.get("members", []):
            if isinstance(m, dict):
                members_data.append(
                    ProjectMember(
                        userId=str(m.get("userId") or m.get("user_id") or ""),
                        role=m.get("role", "member"),
                    )
                )

        return cls(
            id=str(doc.get("_id") or doc.get("id") or ""),
            name=doc.get("name", ""),
            description=doc.get("description"),
            ownerId=str(doc.get("ownerId") or doc.get("owner_id") or ""),
            repo_url=doc.get("repo_url"),
            default_branch=doc.get("default_branch") or "main",
            members=members_data,
            status=doc.get("status") or "active",
            createdAt=doc.get("createdAt") or doc.get("created_at"),
            updatedAt=doc.get("updatedAt") or doc.get("updated_at"),
        )
