"""
FastAPI application entry-point.

Start with:
    uvicorn Backend.main:app --reload
"""
from fastapi import FastAPI

from Backend.auth.router import router as auth_router

app = FastAPI(
    title="AI Software Project Health & Risk Analyzer",
    version="0.1.0",
    description="Backend API for analysing software project health and risk.",
)

# Mount routers
app.include_router(auth_router)


@app.get("/health", tags=["Health"])
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}
