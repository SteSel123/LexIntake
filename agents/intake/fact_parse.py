"""Validate and apply LLM-extracted intake fields (no free-text regex parsing).

Money, dates, and jurisdiction are normalized by the LLM into
``ExtractedIntakeFields``; this module only validates codes/dates and maps
the Pydantic result onto ``IntakeFacts``.
"""

from __future__ import annotations

from datetime import date

from agents.intake.constants import SENTINEL_NAME, SENTINEL_PARTY, US_STATE_CODES
from agents.intake.models import ExtractedIntakeFields, IntakeFacts


def is_iso_date(value: str | None) -> bool:
    """Return True when ``value`` is a real calendar date in ``YYYY-MM-DD`` form."""
    if not value or len(value.strip()) < 10:
        return False
    try:
        date.fromisoformat(value.strip()[:10])
        return True
    except ValueError:
        return False


def is_valid_jurisdiction(value: str | None) -> bool:
    """Return True when ``value`` is a recognized US state / DC code."""
    if not value:
        return False
    return value.strip().upper() in US_STATE_CODES


def apply_extracted_fields(
    extracted: ExtractedIntakeFields,
    *,
    narrative: str,
    base: IntakeFacts | None = None,
) -> IntakeFacts:
    """Map structured LLM output onto ``IntakeFacts`` (LLM → Pydantic → facts)."""
    facts = base.model_copy(deep=True) if base is not None else IntakeFacts()
    text = (narrative or "").strip()
    if text:
        prior = (facts.narrative or "").strip()
        facts.narrative = f"{prior}\n{text}".strip() if prior and prior != text else text

    if extracted.name:
        facts.name = extracted.name
    elif not facts.name:
        facts.name = SENTINEL_NAME

    if extracted.opposing_party:
        facts.opposing_party = extracted.opposing_party
    elif not facts.opposing_party:
        facts.opposing_party = SENTINEL_PARTY

    if extracted.practice_area:
        facts.practice_area = extracted.practice_area
        facts.case_type = extracted.practice_area

    if extracted.jurisdiction and is_valid_jurisdiction(extracted.jurisdiction):
        facts.jurisdiction = extracted.jurisdiction.strip().upper()

    if extracted.incident_date and is_iso_date(extracted.incident_date):
        facts.incident_date = extracted.incident_date.strip()[:10]

    if extracted.damages is not None:
        facts.damages = int(extracted.damages)

    if extracted.severity:
        severity = str(extracted.severity).strip().lower()
        if severity in {"low", "medium", "high"}:
            facts.severity = severity
            facts.priority = severity  # type: ignore[assignment]

    if extracted.uncertain is not None:
        facts.uncertain = bool(extracted.uncertain)

    return facts


def parse_case_description(description: str) -> IntakeFacts:
    """Offline stub: narrative-only facts (no regex inference).

    Prefer ``IntakeAgent.extract_facts`` when an LLM is available so money,
    dates, and jurisdiction come from structured model output.
    """
    text = (description or "").strip()
    return IntakeFacts(
        name=SENTINEL_NAME,
        opposing_party=SENTINEL_PARTY,
        narrative=text or None,
    )
