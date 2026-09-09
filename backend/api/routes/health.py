"""Health and service metadata routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": "lexintake-api",
        "docs": "/docs",
        "health": "/health",
        "intake": "POST /v1/intake/analyze",
        "interview": "POST /v1/interview/sessions",
    }
