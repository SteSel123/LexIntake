"""Fact parsing heuristics."""

from __future__ import annotations

from agents.intake.fact_parse import infer_damages, infer_practice_area, parse_case_description


def test_parse_pi_case_description():
    text = "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago."
    facts = parse_case_description(text)
    assert facts.practice_area == "Personal Injury"
    assert facts.jurisdiction == "CA"
    assert facts.damages == 45_000
    assert facts.incident_date is not None


def test_infer_practice_area_employment():
    assert infer_practice_area("employment discrimination in CA") == "Employment Law"


def test_infer_damages_k_suffix():
    assert infer_damages("estimated damages around 45k") == 45_000
