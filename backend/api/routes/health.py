"""Health and service metadata routes.

Lightweight endpoints for uptime checks and API discovery without invoking
agents or database connections.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return a fixed OK payload for load balancer / k8s probes."""
    return HealthResponse()


@router.get("/")
def root() -> dict[str, str]:
    """Point callers at OpenAPI docs and primary intake/interview paths."""
    return {
        "service": "lexintake-api",
        "docs": "/docs",
        "health": "/health",
        "intake": "POST /v1/intake/analyze",
        "interview": "POST /v1/interview/sessions",
    }
