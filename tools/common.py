"""
Shared helpers for LexIntake Agno tools.

Practice-area normalization, Postgres KB lookups, vector search,
and tool timing/metrics used across all intake screening tools.
"""

from __future__ import annotations

import re
import time as _time
from contextlib import contextmanager
from typing import Any, Iterator

from monitoring.app_logging import get_console_logger, log_optional_failure

logger = get_console_logger("tools")

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Slug aliases for match_practice_area (case_type → KB practice area name).
PRACTICE_AREA_ALIASES: dict[str, str] = {
    "pi": "Personal Injury",
    "personal_injury": "Personal Injury",
    "auto_accident": "Personal Injury",
    "car_accident": "Personal Injury",
    "employment": "Employment Law",
    "wrongful_termination": "Employment Law",
    "wage": "Employment Law",
    "workers_comp": "Workers’ Compensation",
    "workers_compensation": "Workers’ Compensation",
    "med_mal": "Medical Malpractice",
    "medical_malpractice": "Medical Malpractice",
    "product": "Product Liability",
    "products": "Product Liability",
    "criminal": "Criminal Defense",
    "dui": "Criminal Defense",
    "family": "Family Law",
    "divorce": "Family Law",
    "custody": "Family Law",
    "immigration": "Immigration",
    "asylum": "Immigration",
    "civil_rights": "Civil Rights",
    "consumer": "Consumer Protection",
    "fdcpa": "Consumer Protection",
}


def slugify(value: str | None) -> str:
    """Normalize free text to lowercase underscore slug for deterministic matching."""
    if not value:
        return ""
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_")


def attorney_key(name: str | None, *, max_len: int = 80) -> str:
    """Sanitize attorney display name for metrics / logging keys."""
    raw = "".join(ch if ch.isalnum() else "_" for ch in str(name or "").lower())
    return raw[:max_len]


def query_structured(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a read query against PostgreSQL structured tables."""
    try:
        from db.structured_db import query_rows

        return query_rows(sql, params)
    except Exception as exc:  # noqa: BLE001
        logger.error("Structured query failed: %s", exc)
        return []


def load_practice_areas() -> list[str]:
    """Load practice area names from Postgres (seeded from kb/practice_areas.json)."""
    rows = query_structured("SELECT name FROM practice_areas ORDER BY name")
    return [str(r["name"]) for r in rows if r.get("name")]


def load_acceptance_criteria(practice_area: str | None) -> dict[str, Any] | None:
    """Load acceptance payload for one practice area from Postgres."""
    if not practice_area:
        return None
    rows = query_structured(
        "SELECT payload FROM acceptance_criteria WHERE practice_area = :area",
        {"area": practice_area},
    )
    if rows and isinstance(rows[0].get("payload"), dict):
        return rows[0]["payload"]
    # Fallback: slug match when canonical practice_area name differs from caller input.
    all_rows = query_structured("SELECT practice_area, payload FROM acceptance_criteria")
    needle = slugify(practice_area)
    for row in all_rows:
        if slugify(str(row.get("practice_area") or "")) == needle and isinstance(
            row.get("payload"), dict
        ):
            return row["payload"]
    return None


def match_practice_area(case_type: str) -> str | None:
    """Map a practice-area label to a KB name (exact slug or alias only).

    Free-text narratives are classified by the LLM into ``ExtractedIntakeFields``;
    this helper only resolves already-normalized labels to canonical KB names.
    """
    if not case_type:
        return None
    areas = load_practice_areas()
    needle = slugify(case_type)
    if not needle:
        return None

    for area in areas:
        if slugify(area) == needle:
            return area

    if needle in PRACTICE_AREA_ALIASES:
        aliased = PRACTICE_AREA_ALIASES[needle]
        for area in areas:
            if slugify(area) == slugify(aliased):
                return area
        return aliased

    return None


def lookup_sol_rule(practice_area: str, jurisdiction: str) -> dict[str, Any] | None:
    """Lookup SOL rule from Postgres (seeded from kb/sol_tables.json).

    Returns ``{rule_text, duration_days, open_ended}`` or ``None``.
    """
    jur = jurisdiction.strip().upper()
    rows = query_structured(
        """
        SELECT rule_text, duration_days, open_ended
        FROM sol_rules
        WHERE practice_area = :area AND jurisdiction = :jur
        LIMIT 1
        """,
        {"area": practice_area, "jur": jur},
    )
    if not rows:
        all_rows = query_structured(
            """
            SELECT practice_area, jurisdiction, rule_text, duration_days, open_ended
            FROM sol_rules WHERE jurisdiction = :jur
            """,
            {"jur": jur},
        )
        needle = slugify(practice_area)
        rows = [
            row
            for row in all_rows
            if slugify(str(row.get("practice_area") or "")) == needle
        ]
    if not rows:
        return None
    row = rows[0]
    duration = row.get("duration_days")
    return {
        "rule_text": str(row.get("rule_text") or ""),
        "duration_days": int(duration) if duration is not None else None,
        "open_ended": bool(row.get("open_ended", False)),
    }


def vector_search(
    query: str,
    top_k: int = 5,
    practice_area: str | None = None,
    jurisdiction: str | None = None,
    doc_type: str | None = None,
    *,
    log: bool = True,
) -> list[dict[str, Any]]:
    """Search PostgreSQL kb_docs (pgvector); returns [] on any failure."""
    try:
        from db.pgvector_store import count_rows, search_kb_docs
        from etl.transform.embeddings import get_embedder

        embedder = get_embedder()
        vector = embedder.embed([query])[0]
        hits = search_kb_docs(
            vector,
            top_k=top_k,
            practice_area=practice_area,
            jurisdiction=jurisdiction,
            doc_type=doc_type,
        )
        if log:
            try:
                total = count_rows()
                from monitoring.logger import log_retrieval

                log_retrieval(query, hits=len(hits), total_chunks=total)
            except Exception as exc:  # noqa: BLE001
                log_optional_failure(logger, "retrieval metrics", exc)
        return hits
    except (ImportError, RuntimeError, ValueError, OSError) as exc:
        logger.warning("Vector search unavailable: %s: %s", type(exc).__name__, exc)
        if log:
            try:
                from monitoring.logger import log_retrieval

                log_retrieval(query, hits=0, total_chunks=0)
            except Exception as exc:  # noqa: BLE001
                log_optional_failure(logger, "empty retrieval metrics", exc)
        return []


@contextmanager
def tool_timer(tool_name: str) -> Iterator[None]:
    """Import-safe tool latency/success logger (no payloads)."""
    start = _time.perf_counter()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        try:
            from monitoring.logger import log_tool_call

            log_tool_call(tool_name, success, (_time.perf_counter() - start) * 1000.0)
        except Exception as exc:  # noqa: BLE001
            log_optional_failure(logger, f"tool_timer({tool_name})", exc)
