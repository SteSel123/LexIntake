"""
Agno tool: conflict check against structured clients table.

Searches existing client records for name overlap with the prospective client
or opposing party. Uses substring matching (not exact-only) to catch variants.
"""

from __future__ import annotations

from typing import Any

from agno.tools import tool
from pydantic import BaseModel, Field

from tools.common import logger, query_structured, tool_timer


class ConflictCheckInput(BaseModel):
    """Prospective client and opposing party names to screen."""

    name: str = Field(..., description="Prospective client name")
    opposing_party: str = Field(..., description="Known opposing party name")


class ConflictMatch(BaseModel):
    """One client row that matched a screening target."""

    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    state: str | None = None
    matched_on: str


class ConflictCheckOutput(BaseModel):
    """Conflict screening result; conflict=True triggers hard reject in scoring."""

    conflict: bool
    details: list[ConflictMatch]
    explanation: str = ""


def _normalize(value: str) -> str:
    """Case-insensitive, whitespace-collapsed name for fuzzy equality checks."""
    return " ".join(value.casefold().split())


@tool(
    name="conflict_check",
    description=(
        "Search the clients database for conflicts with the prospective client "
        "name or opposing party (case-insensitive)."
    ),
)
def conflict_check(payload: ConflictCheckInput) -> ConflictCheckOutput:
    """Case-insensitive conflict search over structured clients."""
    with tool_timer("conflict_check"):
        return _conflict_check_impl(payload)


def _conflict_check_impl(payload: ConflictCheckInput) -> ConflictCheckOutput:
    """Core conflict logic; wrapped by Agno tool for timing and error boundaries."""
    try:
        rows = query_structured(
            "SELECT id, name, email, phone, state FROM clients ORDER BY name"
        )
        if not rows:
            return ConflictCheckOutput(
                conflict=False,
                details=[],
                explanation="Clients table is empty or unavailable. No conflicts found; verify manually if needed.",
            )

        targets = {
            "prospective_client": _normalize(payload.name),
            "opposing_party": _normalize(payload.opposing_party),
        }
        matches: list[ConflictMatch] = []

        for row in rows:
            client_name = _normalize(str(row["name"] or ""))
            if not client_name:
                continue
            for label, target in targets.items():
                if not target:
                    continue
                # Bidirectional substring match catches partial / reversed name forms.
                if target == client_name or target in client_name or client_name in target:
                    matches.append(
                        ConflictMatch(
                            id=str(row["id"]),
                            name=str(row["name"]),
                            email=row["email"],
                            phone=row["phone"],
                            state=row["state"],
                            matched_on=label,
                        )
                    )
                    break

        # Stable deterministic ordering
        matches.sort(key=lambda m: (m.matched_on, m.name.casefold(), m.id))
        return ConflictCheckOutput(
            conflict=bool(matches),
            details=matches,
            explanation=(
                f"Found {len(matches)} potential conflict(s)."
                if matches
                else "No conflicting client records matched name or opposing_party."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("conflict_check failed: %s", exc)
        return ConflictCheckOutput(
            conflict=False,
            details=[],
            explanation=f"Tool error fallback: {exc}. Manual conflict check required.",
        )


if __name__ == "__main__":
    sample: dict[str, Any] = {"name": "Elena Vasquez", "opposing_party": "Acme Corp"}
    print(conflict_check.entrypoint(ConflictCheckInput(**sample)))
