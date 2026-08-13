"""Agno tool: estimate case value from past_cases (+ vector fallback)."""

from __future__ import annotations

from statistics import mean

from agno.tools import tool
from pydantic import BaseModel, Field

from common import get_sqlite_connection, logger, match_practice_area, slugify, tool_timer, vector_search

SEVERITY_FACTORS = {
    "low": 0.75,
    "medium": 1.0,
    "high": 1.35,
    "catastrophic": 1.75,
}


class EstimateCaseValueInput(BaseModel):
    case_type: str = Field(..., description="Practice area or case type")
    severity: str = Field(..., description="low | medium | high | catastrophic")
    damages: int = Field(..., ge=0, description="Claimed or estimated specials in USD")


class EstimateCaseValueOutput(BaseModel):
    estimate: float
    range_low: float
    range_high: float
    explanation: str


def _severity_factor(severity: str) -> float:
    return SEVERITY_FACTORS.get(slugify(severity), 1.0)


def _amounts_from_sqlite(practice_area: str) -> list[float]:
    conn = get_sqlite_connection()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT settlement_amount, practice_area
            FROM past_cases
            WHERE settlement_amount IS NOT NULL AND settlement_amount > 0
            ORDER BY id
            """
        ).fetchall()
    finally:
        conn.close()

    target = slugify(practice_area)
    amounts = [
        float(row["settlement_amount"])
        for row in rows
        if slugify(str(row["practice_area"])) == target
    ]
    return amounts


def _amounts_from_vector(case_type: str, practice_area: str | None) -> list[float]:
    hits = vector_search(
        query=f"{case_type} settlement award comparable cases",
        top_k=8,
        practice_area=practice_area,
    )
    amounts: list[float] = []
    for hit in hits:
        text = str(hit.get("text") or "")
        # Deterministic parse of integer dollar-like tokens already present as JSON numbers
        for token in text.replace(",", " ").split():
            if token.isdigit():
                value = int(token)
                if 1000 <= value <= 50_000_000:
                    amounts.append(float(value))
    return amounts


def _build_estimate(amounts: list[float], damages: int, severity: str) -> tuple[float, float, float]:
    factor = _severity_factor(severity)
    base = mean(amounts)
    # Blend comps with stated damages (deterministic weights)
    blended = (0.7 * base) + (0.3 * float(damages))
    estimate = round(blended * factor, 2)
    spread = 0.25 if len(amounts) >= 2 else 0.35
    low = round(estimate * (1.0 - spread), 2)
    high = round(estimate * (1.0 + spread), 2)
    return estimate, low, high


@tool(
    name="estimate_case_value",
    description=(
        "Estimate settlement value from comparable past_cases, with vector KB fallback "
        "when structured comps are missing."
    ),
)
def estimate_case_value(payload: EstimateCaseValueInput) -> EstimateCaseValueOutput:
    """Deterministic settlement estimate from comps / vector fallback."""
    with tool_timer("estimate_case_value"):
        return _estimate_case_value_impl(payload)


def _estimate_case_value_impl(payload: EstimateCaseValueInput) -> EstimateCaseValueOutput:
    try:
        practice_area = match_practice_area(payload.case_type) or payload.case_type
        amounts = _amounts_from_sqlite(practice_area)
        source = "past_cases"

        if not amounts:
            amounts = _amounts_from_vector(payload.case_type, practice_area)
            source = "vector_fallback"

        if not amounts:
            return EstimateCaseValueOutput(
                estimate=0.0,
                range_low=0.0,
                range_high=0.0,
                explanation=(
                    "insufficient data: no comparable settlements in past_cases or vector DB "
                    f"for case_type '{payload.case_type}'."
                ),
            )

        estimate, low, high = _build_estimate(amounts, payload.damages, payload.severity)
        return EstimateCaseValueOutput(
            estimate=estimate,
            range_low=low,
            range_high=high,
            explanation=(
                f"Used {len(amounts)} comparable amount(s) via {source} for '{practice_area}'. "
                f"severity_factor={_severity_factor(payload.severity)}, damages={payload.damages}. "
                f"Estimate ${estimate:,.2f} (range ${low:,.2f}–${high:,.2f})."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("estimate_case_value failed: %s", exc)
        return EstimateCaseValueOutput(
            estimate=0.0,
            range_low=0.0,
            range_high=0.0,
            explanation=f"insufficient data: tool error fallback ({exc}).",
        )


if __name__ == "__main__":
    print(
        estimate_case_value.entrypoint(
            EstimateCaseValueInput(case_type="Personal Injury", severity="high", damages=50000)
        )
    )
