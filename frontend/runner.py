"""Compatibility shim — prefer ``backend.services.intake_service``."""

from __future__ import annotations

from backend.services.intake_service import (  # noqa: F401
    LEGAL_DISCLAIMER,
    build_result_payload,
    run_intake_analysis,
)

__all__ = [
    "LEGAL_DISCLAIMER",
    "build_result_payload",
    "run_intake_analysis",
]
