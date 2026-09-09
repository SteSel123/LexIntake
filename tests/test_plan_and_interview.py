"""Tests for extracted plan phase and interview sentinel helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.intake.constants import FALLBACK_TOOL_NAME, SENTINEL_NAME, SENTINEL_PARTY
from agents.intake.models import IntakeFacts
from agents.intake.plan import build_plan
from agents.interview.agent import InterviewSession


def test_build_plan_schedules_core_tools():
    facts = IntakeFacts(
        name="Alex",
        opposing_party="City Transit",
        practice_area="Personal Injury",
        case_type="Personal Injury",
        jurisdiction="CA",
        incident_date="2025-06-01",
        damages=45_000,
        narrative="Rear-end collision",
    )
    with patch("agents.intake.plan.match_practice_area", return_value="Personal Injury"):
        plan = build_plan(facts)
    assert "check_statute_of_limitations" in plan.tools_to_call
    assert "conflict_check" in plan.tools_to_call
    assert "estimate_case_value" in plan.tools_to_call
    assert "route_lead" in plan.tools_to_call


def test_build_plan_uses_kb_docs_fallback_when_area_unknown():
    facts = IntakeFacts(name="A", opposing_party="B", case_type="obscure_unmapped_matter_xyz")
    with patch("agents.intake.plan.match_practice_area", return_value=None):
        plan = build_plan(facts)
    assert FALLBACK_TOOL_NAME in plan.tools_to_call


def test_interview_missing_fields_treats_sentinels_as_incomplete():
    session = InterviewSession(agent=MagicMock())
    session.facts = IntakeFacts(name=SENTINEL_NAME, opposing_party=SENTINEL_PARTY)
    missing = session.missing_fields()
    assert "name" in missing
    assert "opposing_party" in missing
