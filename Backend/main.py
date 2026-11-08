"""
FastAPI Application — AI Software Project Health & Risk Analyzer
-----------------------------------------------------------------
Entry point. Responsible for:
  - Application lifecycle (startup/shutdown)
  - Middleware configuration
  - Router registration
  - Global exception handling

All business logic lives in the router modules:
  Backend/auth/router.py            – /auth/*
  Backend/routers/project_router.py – /api/projects  (CRUD)
  Backend/routers/data_sync_router.py – /api/projects/{id}/contributors | commits

Start with:
    uvicorn Backend.main:app --reload
"""

import logging
import logging.config
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from Backend.auth.router import router as auth_router
from Backend.database import ensure_indexes
from Backend.persistence import DatabaseError
from Backend.routers.data_sync_router import router as data_sync_router
from Backend.routers.project_router import router as project_router
from Backend.routers.threshold_router import router as threshold_router


# ---------------------------------------------------------------------------
# Logging — configure once at startup with a secret-masking filter
# ---------------------------------------------------------------------------

_SECRET_PATTERN = re.compile(
    r"(token|password|secret|key|authorization|mongo_uri)\s*[=:]\s*\S+",
    re.IGNORECASE,
)
_REDACTED = r"\1=<REDACTED>"


class _SecretMaskingFilter(logging.Filter):
    """Strip accidental secret values from log records before they are emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SECRET_PATTERN.sub(_REDACTED, str(record.msg))
        record.args = tuple(
            _SECRET_PATTERN.sub(_REDACTED, str(a)) if isinstance(a, str) else a
            for a in (record.args or ())
        )
        return True


def _configure_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Apply secret-masking filter to the root logger so every handler inherits it.
    secret_filter = _SecretMaskingFilter()
    logging.getLogger().addFilter(secret_filter)


_configure_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    ensure_indexes()
    yield


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Software Project Health & Risk Analyzer",
    version="0.1.0",
    description="Backend API for analysing software project health and risk.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    """
    Convert DatabaseError (MongoDB connectivity / driver failures) into a
    503 Service Unavailable response.  The full error is logged server-side;
    the client only receives a safe, generic message.
    """
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "error": "service_unavailable",
            "detail": str(exc),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for any exception that is not explicitly handled.
    Logs the full traceback server-side, returns a generic 500 to the client
    so internal implementation details are never leaked.
    """
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred. Please try again later.",
        },
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# Read allowed origins from environment — default to localhost for development.
# In production set: CORS_ALLOWED_ORIGINS=https://yourfrontend.com
_raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(project_router)
app.include_router(data_sync_router)
app.include_router(threshold_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["Health"])
@app.get("/health", tags=["Health"])
def health_check():
    """Basic liveness probe endpoint."""
    return {"status": "healthy"}
