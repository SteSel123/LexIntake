"""Quick intake analysis endpoints.

Single-request screening: client sends a case description and receives a
scored decision without maintaining session state.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import AnalyzeRequest, AnalyzeResponse
from backend.services.intake_service import run_intake_analysis
from monitoring.app_logging import get_console_logger

router = APIRouter(prefix="/v1/intake", tags=["intake"])
_logger = get_console_logger("api.intake")


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """Run the full intake agent + scoring pipeline on ``body.description``."""
    description = body.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="description must not be empty")
    try:
        payload = run_intake_analysis(description)
    except Exception as exc:  # noqa: BLE001 — surface unexpected pipeline failures
        _logger.exception("Intake analysis failed")
        raise HTTPException(status_code=500, detail=f"Intake analysis failed: {exc}") from exc
    return AnalyzeResponse.model_validate(payload)
