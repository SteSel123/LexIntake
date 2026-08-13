"""Demo script: run 4 predefined LexIntake intake scenarios."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

UI_DIR = Path(__file__).resolve().parent
ROOT = UI_DIR.parent
for path in (str(ROOT), str(UI_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from runner import LEGAL_DISCLAIMER, run_intake_analysis

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "pi_valid",
        "name": "Valid Personal Injury Case",
        "input": (
            "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago."
        ),
        "expect": {
            "qualified": True,
            "priority": "High",
            "decision": "SCHEDULE_CONSULT",
        },
    },
    {
        "id": "sol_expired",
        "name": "SOL Expired Case",
        "input": "Slip-and-fall in NV, incident 4 years ago, moderate injuries.",
        "expect": {
            "qualified": False,
            "decision": "REJECT",
            "explanation_contains": ["sol", "statute", "expir"],
        },
    },
    {
        "id": "conflict",
        "name": "Conflict Case",
        "input": "Employment discrimination claim in CA, opposing party is ACME Corp.",
        "expect": {
            "decision_in": ["REJECT", "REVIEW"],
            "conflict_or_escalate": True,
        },
    },
    {
        "id": "uncertain",
        "name": "Uncertain Case → Human Review",
        "input": (
            "Immigration matter with unclear facts, missing dates, missing jurisdiction."
        ),
        "expect": {
            "decision": "REVIEW",
            "escalate": True,
        },
    },
]


def _contains_any(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return any(n.lower() in lower for n in needles)


def verify_guardrails(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    explanation = str(payload.get("explanation") or "")
    if "not legal advice" not in explanation.lower():
        issues.append("missing_disclaimer_in_explanation")
    citations = payload.get("citations") or []
    if not citations:
        issues.append("missing_citations")
    else:
        for c in citations:
            if not c.get("chunk_id"):
                issues.append("citation_missing_chunk_id")
                break
    return issues


def verify_scenario(scenario: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    expect = scenario["expect"]

    if "qualified" in expect and bool(payload.get("qualified")) != bool(expect["qualified"]):
        issues.append(
            f"qualified expected={expect['qualified']} got={payload.get('qualified')}"
        )
    if "priority" in expect and payload.get("priority") != expect["priority"]:
        issues.append(
            f"priority expected={expect['priority']} got={payload.get('priority')}"
        )
    if "decision" in expect and payload.get("decision") != expect["decision"]:
        issues.append(
            f"decision expected={expect['decision']} got={payload.get('decision')}"
        )
    if "decision_in" in expect and payload.get("decision") not in expect["decision_in"]:
        issues.append(
            f"decision expected in {expect['decision_in']} got={payload.get('decision')}"
        )
    if "explanation_contains" in expect:
        if not _contains_any(str(payload.get("explanation") or ""), expect["explanation_contains"]):
            issues.append("explanation missing SOL expiration language")
    if expect.get("escalate") and not payload.get("escalate"):
        issues.append("expected escalation=true")
    if expect.get("conflict_or_escalate"):
        conflict = ((payload.get("tool_results") or {}).get("conflict") or {}).get("conflict")
        if not (conflict or payload.get("escalate") or payload.get("decision") in {"REJECT", "REVIEW"}):
            issues.append("expected conflict detection or escalate/reject/review")

    issues.extend(verify_guardrails(payload))
    return issues


def main() -> None:
    print("LexIntake UI demo scenarios")
    print("=" * 72)
    print(f"Disclaimer check string: {LEGAL_DISCLAIMER}")
    print()

    passed = 0
    for scenario in SCENARIOS:
        print(f"## {scenario['name']}")
        print(f"Input: {scenario['input']}")
        payload = run_intake_analysis(scenario["input"])
        print(
            {
                "qualified": payload.get("qualified"),
                "lead_score": payload.get("lead_score"),
                "priority": payload.get("priority"),
                "decision": payload.get("decision"),
                "recommended_attorney": payload.get("recommended_attorney"),
                "escalate": payload.get("escalate"),
                "citations": len(payload.get("citations") or []),
                "latency_ms": payload.get("latency_ms"),
            }
        )
        issues = verify_scenario(scenario, payload)
        grounding_ok = bool(payload.get("citations"))
        print(f"Grounding (KB citations present): {grounding_ok}")
        print(f"Escalation flag: {bool(payload.get('escalate'))}")
        if issues:
            print(f"FAIL issues={issues}")
        else:
            print("PASS")
            passed += 1
        print("-" * 72)

    total = len(SCENARIOS)
    print(f"Demo complete: {passed}/{total} scenarios passed")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
