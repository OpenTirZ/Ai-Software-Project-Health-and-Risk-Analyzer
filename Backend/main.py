"""
FastAPI Application — Contributor Feature
-------------------------------------------
API layer for the AI Software Project Health & Risk Analyzer.

Contributor endpoints:
    GET  /api/projects/{project_id}/contributors
    POST /api/projects/{project_id}/sync-contributors
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from Backend.persistence import get_project, get_project_contributors
from Backend.contributor_service import (
    sync_project_contributors,
    ProjectNotFoundError,
    ProjectRepoNotConfiguredError,
    RepoMismatchError,
)
from Backend.github_commits import (
    GitHubTokenMissingError,
    GitHubAuthError,
    GitHubRepoNotFoundError,
    GitHubAPIError,
)
from Backend.database import ensure_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    ensure_indexes()
    yield


app = FastAPI(
    title="AI Software Project Health & Risk Analyzer",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SyncContributorsRequest(BaseModel):
    repo_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Contributor endpoints
# ---------------------------------------------------------------------------

@app.get("/api/projects/{project_id}/contributors")
def get_contributors(project_id: str):
    """
    Retrieve stored contributors for a project.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return get_project_contributors(project_id)


@app.post("/api/projects/{project_id}/sync-contributors")
def sync_contributors(project_id: str, request: SyncContributorsRequest):
    """
    Sync contributors from GitHub for the given project.

    Uses the project's configured repository URL.  If ``repo_url`` is
    provided in the request body it is validated against the project's
    stored configuration.
    """
    try:
        result = sync_project_contributors(
            project_id=project_id,
            repo_url=request.repo_url,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProjectRepoNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RepoMismatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GitHubTokenMissingError:
        raise HTTPException(
            status_code=500,
            detail="GitHub token is not configured on the server.",
        )
    except GitHubAuthError:
        raise HTTPException(
            status_code=401,
            detail="GitHub authentication failed. Check the configured token.",
        )
    except GitHubRepoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
