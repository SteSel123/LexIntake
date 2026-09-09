"""Application services shared by the API and CLI demos."""

from backend.services.intake_service import (
    LEGAL_DISCLAIMER,
    build_result_payload,
    run_intake_analysis,
)

__all__ = [
    "LEGAL_DISCLAIMER",
    "build_result_payload",
    "run_intake_analysis",
]
