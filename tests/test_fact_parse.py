"""Tests for intake fact helpers: validators + LLM ExtractedIntakeFields mapping."""

from __future__ import annotations

from agents.intake.constants import SENTINEL_NAME, SENTINEL_PARTY, US_STATE_CODES
from agents.intake.fact_parse import (
    apply_extracted_fields,
    is_iso_date,
    is_valid_jurisdiction,
    parse_case_description,
)
from agents.intake.models import ExtractedIntakeFields


def test_parse_case_description_is_narrative_stub():
    text = "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago."
    facts = parse_case_description(text)
    assert facts.narrative == text
    assert facts.name == SENTINEL_NAME
    assert facts.opposing_party == SENTINEL_PARTY
    assert facts.jurisdiction is None
    assert facts.damages is None
    assert facts.incident_date is None


def test_apply_extracted_fields_maps_llm_output():
    extracted = ExtractedIntakeFields(
        name="Elena Vasquez",
        opposing_party="ACME Corp",
        practice_area="Personal Injury",
        jurisdiction="ca",
        incident_date="2024-06-15",
        damages=45_000,
        severity="high",
        uncertain=True,
    )
    facts = apply_extracted_fields(
        extracted,
        narrative="Rear-end collision in California, $45k damages.",
    )
    assert facts.name == "Elena Vasquez"
    assert facts.opposing_party == "ACME Corp"
    assert facts.practice_area == "Personal Injury"
    assert facts.case_type == "Personal Injury"
    assert facts.jurisdiction == "CA"
    assert facts.incident_date == "2024-06-15"
    assert facts.damages == 45_000
    assert facts.severity == "high"
    assert facts.priority == "high"
    assert facts.uncertain is True
    assert "Rear-end" in (facts.narrative or "")


def test_apply_extracted_fields_rejects_invalid_jurisdiction_and_date():
    extracted = ExtractedIntakeFields(
        jurisdiction="PE",
        incident_date="06/15/2024",
        damages=1000,
    )
    facts = apply_extracted_fields(extracted, narrative="test")
    assert facts.jurisdiction is None
    assert facts.incident_date is None
    assert facts.damages == 1000


def test_is_iso_date():
    assert is_iso_date("2024-06-15")
    assert not is_iso_date("06/15/2024")
    assert not is_iso_date("not-a-date")


def test_is_valid_jurisdiction():
    assert is_valid_jurisdiction("CA")
    assert is_valid_jurisdiction("ny")
    assert "DC" in US_STATE_CODES
    assert not is_valid_jurisdiction("PE")
    assert not is_valid_jurisdiction("no")
    assert not is_valid_jurisdiction(None)
