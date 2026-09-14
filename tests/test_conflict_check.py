"""Tests for ``tools.conflict_check`` with a mocked structured Postgres layer.

Validates conflict detection when a prospect name matches a seeded client row.
"""

from __future__ import annotations

from unittest.mock import patch

from tools.conflict_check import ConflictCheckInput, _conflict_check_impl


@patch("tools.conflict_check.query_structured")
def test_conflict_check_finds_match(mock_query):
    mock_query.return_value = [
        {"id": "c1", "name": "Elena Vasquez", "email": "e@v.com", "phone": None, "state": "CA"}
    ]
    out = _conflict_check_impl(
        ConflictCheckInput(name="Elena Vasquez", opposing_party="ACME Corp")
    )
    assert out.conflict is True
    assert out.details


@patch("tools.conflict_check.query_structured")
def test_conflict_check_no_match(mock_query):
    mock_query.return_value = [
        {"id": "c1", "name": "Unrelated Client", "email": None, "phone": None, "state": "NV"}
    ]
    out = _conflict_check_impl(
        ConflictCheckInput(name="New Prospect", opposing_party="Other Corp")
    )
    assert out.conflict is False
