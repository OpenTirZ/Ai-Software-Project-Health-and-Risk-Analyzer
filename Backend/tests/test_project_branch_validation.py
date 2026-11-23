"""Regression tests for Git branch-name validation in project schemas."""

import pytest
from pydantic import ValidationError

from Backend.schemas.project_schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
)


@pytest.mark.parametrize(
    "branch",
    ["feature/login", "release/v1.2", "bugfix-123", "main"],
)
def test_create_project_accepts_valid_branch_names(branch):
    project = CreateProjectRequest(name="Analyzer", default_branch=branch)
    assert project.default_branch == branch


@pytest.mark.parametrize(
    "branch",
    [
        "/feature/login",
        "feature//login",
        "feature/../main",
        "feature/.hidden",
        "feature/name.",
        "feature/lock.lock",
        "feature/@{1}",
        "@",
    ],
)
def test_create_project_rejects_invalid_git_branch_names(branch):
    with pytest.raises(ValidationError):
        CreateProjectRequest(name="Analyzer", default_branch=branch)


def test_update_project_rejects_invalid_git_branch_names():
    with pytest.raises(ValidationError):
        UpdateProjectRequest(default_branch="feature//login")
