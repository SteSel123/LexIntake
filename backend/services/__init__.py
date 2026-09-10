"""Application services shared by the API and CLI demos.

Re-exports the intake analysis helpers so callers import from a stable
``backend.services`` namespace instead of reaching into implementation modules.
"""

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
