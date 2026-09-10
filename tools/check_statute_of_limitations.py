"""
Agno tool: check statute of limitations from Postgres sol_rules.

Determines whether a claim is still within the filing deadline using KB rules
seeded from kb/sol_tables.json. Returns conservative fallbacks when data is
missing or unparsable so intake can escalate instead of auto-rejecting.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from agno.tools import tool
from pydantic import BaseModel, Field

from tools.common import logger, lookup_sol_rule, match_practice_area, parse_sol_duration_days, tool_timer


class CheckSOLInput(BaseModel):
    """Required fields for SOL screening."""

    jurisdiction: str = Field(..., description="Two-letter US state code, e.g. CA")
    case_type: str = Field(..., description="Practice area or case type label")
    incident_date: str = Field(..., description="Incident date in ISO format YYYY-MM-DD")


class CheckSOLOutput(BaseModel):
    """SOL result consumed by lead scoring and intake agents."""

    valid: bool
    expires_in: int = Field(..., description="Days remaining; -1 if open-ended or unknown")
    explanation: str


def _parse_incident_date(value: str) -> date | None:
    """Parse ISO date prefix; returns None on malformed input."""
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _today() -> date:
    """UTC date for consistent remaining-days calculation across environments."""
    return datetime.now(timezone.utc).date()


@tool(
    name="check_statute_of_limitations",
    description=(
        "Determine whether a claim is still within the statute of limitations "
        "using jurisdiction, case type, and incident date from the knowledge base."
    ),
)
def check_statute_of_limitations(payload: CheckSOLInput) -> CheckSOLOutput:
    """Check SOL validity against Postgres sol_rules (seeded from kb/sol_tables.json)."""
    with tool_timer("check_statute_of_limitations"):
        return _check_statute_of_limitations_impl(payload)


def _check_statute_of_limitations_impl(payload: CheckSOLInput) -> CheckSOLOutput:
    """Core SOL logic; wrapped by Agno tool for timing and error boundaries."""
    try:
        incident = _parse_incident_date(payload.incident_date)
        if incident is None:
            return CheckSOLOutput(
                valid=False,
                expires_in=-1,
                explanation=(
                    f"Invalid incident_date '{payload.incident_date}'. "
                    "Expected ISO date YYYY-MM-DD. Manual attorney review required."
                ),
            )

        practice_area = match_practice_area(payload.case_type)
        # Unknown practice area → valid=True, expires_in=-1: do not hard-reject on
        # missing KB mapping; scoring will flag missing data for human review.
        if not practice_area:
            return CheckSOLOutput(
                valid=True,
                expires_in=-1,
                explanation=(
                    f"Fallback: no practice area match for case_type '{payload.case_type}'. "
                    "KB lacks a mapped SOL rule; treat as unknown and require attorney review."
                ),
            )

        rule = lookup_sol_rule(practice_area, payload.jurisdiction)
        if not rule:
            return CheckSOLOutput(
                valid=True,
                expires_in=-1,
                explanation=(
                    f"Fallback: no SOL rule in KB for {practice_area} / "
                    f"{payload.jurisdiction.upper()}. Manual verification required."
                ),
            )

        duration_days, open_ended = parse_sol_duration_days(rule)
        if open_ended:
            return CheckSOLOutput(
                valid=True,
                expires_in=-1,
                explanation=(
                    f"{practice_area} in {payload.jurisdiction.upper()} has no fixed filing SOL "
                    f"in KB ('{rule[:160]}'). Claim remains potentially valid."
                ),
            )

        if duration_days is None:
            return CheckSOLOutput(
                valid=True,
                expires_in=-1,
                explanation=(
                    f"Fallback: SOL text found for {practice_area}/{payload.jurisdiction.upper()} "
                    f"but duration could not be parsed deterministically. Rule: {rule[:200]}"
                ),
            )

        deadline = date.fromordinal(incident.toordinal() + duration_days)
        remaining = (deadline - _today()).days
        valid = remaining >= 0
        return CheckSOLOutput(
            valid=valid,
            expires_in=remaining,
            explanation=(
                f"{practice_area} / {payload.jurisdiction.upper()}: period={duration_days} days "
                f"from {incident.isoformat()} to deadline {deadline.isoformat()}. "
                f"{'Within' if valid else 'Outside'} SOL. Source: {rule[:180]}"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("check_statute_of_limitations failed: %s", exc)
        return CheckSOLOutput(
            valid=True,
            expires_in=-1,
            explanation=f"Tool error fallback: {exc}. Manual SOL review required.",
        )


if __name__ == "__main__":
    result = check_statute_of_limitations.entrypoint(
        CheckSOLInput(jurisdiction="CA", case_type="Personal Injury", incident_date="2025-01-15")
    )
    print(result)
