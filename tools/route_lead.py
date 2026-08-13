"""Agno tool: route intake lead to an attorney."""

from __future__ import annotations

import json
from typing import Any

from agno.tools import tool
from pydantic import BaseModel, Field

from common import (
    get_sqlite_connection,
    load_practice_areas,
    logger,
    match_practice_area,
    slugify,
    tool_timer,
)

PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}


class RouteLeadInput(BaseModel):
    practice_area: str = Field(..., description="Target practice area")
    priority: str = Field(..., description="low | medium | high")


class RouteLeadOutput(BaseModel):
    attorney_name: str
    motivation: str


def _jurisdictions(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        pass
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _practice_area_from_attorney_id(attorney_id: str) -> str | None:
    if not attorney_id.startswith("att-"):
        return None
    rest = attorney_id[4:]
    for area in sorted(load_practice_areas(), key=lambda a: len(slugify(a)), reverse=True):
        prefix = f"{slugify(area)}-"
        if rest.startswith(prefix):
            return area
    return None


def _is_available(availability: str | None, priority: str) -> bool:
    status = slugify(availability or "")
    if status in {"accepting_new_clients"}:
        return True
    if status in {"limited", "selective"} and PRIORITY_RANK.get(slugify(priority), 0) >= 2:
        return True
    if status in {"waitlist"} and PRIORITY_RANK.get(slugify(priority), 0) >= 3:
        return True
    return False


@tool(
    name="route_lead",
    description=(
        "Assign an attorney for a lead using practice area, availability, "
        "lowest caseload, then highest experience."
    ),
)
def route_lead(payload: RouteLeadInput) -> RouteLeadOutput:
    """Route lead to best-fit attorney from structured DB."""
    with tool_timer("route_lead"):
        return _route_lead_impl(payload)


def _route_lead_impl(payload: RouteLeadInput) -> RouteLeadOutput:
    try:
        conn = get_sqlite_connection()
        if conn is None:
            return RouteLeadOutput(
                attorney_name="",
                motivation="Fallback: structured DB unavailable. Manual routing required.",
            )

        practice_area = match_practice_area(payload.practice_area) or payload.practice_area
        attorneys = conn.execute(
            """
            SELECT id, name, specialization, experience_years, jurisdictions, availability
            FROM attorneys
            ORDER BY name
            """
        ).fetchall()

        caseload_rows = conn.execute(
            """
            SELECT attorney_id, COUNT(*) AS case_count
            FROM past_cases
            WHERE attorney_id IS NOT NULL
            GROUP BY attorney_id
            """
        ).fetchall()
        conn.close()

        caseload = {str(r["attorney_id"]): int(r["case_count"]) for r in caseload_rows}
        area_slug = slugify(practice_area)

        candidates: list[dict[str, Any]] = []
        for row in attorneys:
            specialization = str(row["specialization"] or "")
            attorney_id = str(row["id"])
            id_area = _practice_area_from_attorney_id(attorney_id)
            matches_area = bool(id_area and slugify(id_area) == area_slug)

            if not matches_area:
                tokens = set(area_slug.split("_")) - {"law"}
                spec_tokens = set(slugify(specialization).split("_"))
                matches_area = bool(tokens & spec_tokens)

            if not matches_area:
                continue
            if not _is_available(row["availability"], payload.priority):
                continue

            candidates.append(
                {
                    "name": str(row["name"]),
                    "experience_years": int(row["experience_years"] or 0),
                    "caseload": caseload.get(attorney_id, 0),
                    "availability": row["availability"],
                    "specialization": specialization,
                    "jurisdictions": _jurisdictions(row["jurisdictions"]),
                    "id": attorney_id,
                }
            )

        if not candidates:
            return RouteLeadOutput(
                attorney_name="",
                motivation=(
                    f"Fallback: no available attorney for practice_area '{practice_area}' "
                    f"at priority '{payload.priority}'. Place on review queue."
                ),
            )

        # lowest caseload, then most experienced, then stable name
        candidates.sort(
            key=lambda c: (c["caseload"], -c["experience_years"], c["name"].casefold())
        )
        chosen = candidates[0]
        return RouteLeadOutput(
            attorney_name=chosen["name"],
            motivation=(
                f"Assigned {chosen['name']} for {practice_area} "
                f"(priority={slugify(payload.priority)}). "
                f"caseload={chosen['caseload']}, experience_years={chosen['experience_years']}, "
                f"availability={chosen['availability']}, specialization={chosen['specialization']}."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("route_lead failed: %s", exc)
        return RouteLeadOutput(
            attorney_name="",
            motivation=f"Fallback: tool error ({exc}). Manual routing required.",
        )


if __name__ == "__main__":
    print(route_lead.entrypoint(RouteLeadInput(practice_area="Personal Injury", priority="high")))
