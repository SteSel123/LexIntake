"""Tests for Postgres-backed KB reference lookups (mocked query layer)."""

from __future__ import annotations

from unittest.mock import patch

from tools.common import load_acceptance_criteria, load_practice_areas, lookup_sol_rule


@patch("tools.common.query_structured")
def test_load_practice_areas_from_postgres(mock_query):
    mock_query.return_value = [
        {"name": "Personal Injury"},
        {"name": "Employment Law"},
    ]
    assert load_practice_areas() == ["Personal Injury", "Employment Law"]


@patch("tools.common.query_structured")
def test_lookup_sol_rule_from_postgres(mock_query):
    mock_query.return_value = [{"rule_text": "2 years from injury (CCP §335.1)."}]
    rule = lookup_sol_rule("Personal Injury", "CA")
    assert rule is not None
    assert "2 years" in rule


@patch("tools.common.query_structured")
def test_load_acceptance_criteria_from_postgres(mock_query):
    mock_query.return_value = [
        {"payload": {"must_have": ["Identifiable at-fault party or liable entity"]}}
    ]
    payload = load_acceptance_criteria("Personal Injury")
    assert payload is not None
    assert "must_have" in payload
