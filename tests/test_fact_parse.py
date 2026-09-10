"""Tests for ``agents.intake.fact_parse`` heuristics on free-text case descriptions.

Covers practice-area inference, damage parsing, date normalization, and PI fields.
"""

from __future__ import annotations

from agents.intake.fact_parse import (
    infer_damages,
    infer_incident_date,
    infer_practice_area,
    is_iso_date,
    parse_case_description,
)


def test_parse_pi_case_description():
    text = "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago."
    facts = parse_case_description(text)
    assert facts.practice_area == "Personal Injury"
    assert facts.jurisdiction == "CA"
    assert facts.damages == 45_000
    assert facts.incident_date is not None
    assert is_iso_date(facts.incident_date)


def test_infer_practice_area_employment():
    assert infer_practice_area("employment discrimination in CA") == "Employment Law"


def test_infer_damages_k_suffix():
    assert infer_damages("estimated damages around 45k") == 45_000


def test_infer_incident_date_iso_and_relative():
    assert infer_incident_date("happened on 2024-06-15") == "2024-06-15"
    assert is_iso_date(infer_incident_date("3 years ago"))


def test_infer_incident_date_common_formats():
    assert infer_incident_date("06/15/2024") == "2024-06-15"
    assert infer_incident_date("15/06/2024") == "2024-06-15"
    assert infer_incident_date("June 15, 2024") == "2024-06-15"
    assert infer_incident_date("15 June 2024") == "2024-06-15"


def test_infer_incident_date_rejects_garbage():
    assert infer_incident_date("last summer sometime") is None
    assert infer_incident_date("not-a-date") is None
    assert not is_iso_date("06/15/2024")
