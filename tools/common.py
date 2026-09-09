"""Shared helpers for LexIntake Agno tools."""

from __future__ import annotations

import re
import time as _time
from contextlib import contextmanager
from typing import Any, Iterator

from monitoring.app_logging import get_console_logger, log_optional_failure

logger = get_console_logger("tools")

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*years?", re.I)
_MONTHS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*months?", re.I)
_DAYS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*days?", re.I)
_NO_SOL_RE = re.compile(r"\bno\s+sol\b|\bno\s+single\s+sol\b", re.I)

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

# Phrase hints for free-text narrative parsing (substring → practice area).
PRACTICE_TEXT_HINTS: tuple[tuple[str, str], ...] = (
    ("personal injury", "Personal Injury"),
    ("rear-end", "Personal Injury"),
    ("slip-and-fall", "Personal Injury"),
    ("slip and fall", "Personal Injury"),
    ("collision", "Personal Injury"),
    ("employment", "Employment Law"),
    ("discrimination", "Employment Law"),
    ("immigration", "Immigration"),
    ("asylum", "Immigration"),
    ("family", "Family Law"),
    ("custody", "Family Law"),
    ("divorce", "Family Law"),
    ("workers", "Workers’ Compensation"),
    ("malpractice", "Medical Malpractice"),
    ("product", "Product Liability"),
    ("civil rights", "Civil Rights"),
    ("consumer", "Consumer Protection"),
    ("criminal", "Criminal Defense"),
)


def slugify(value: str | None) -> str:
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
    all_rows = query_structured("SELECT practice_area, payload FROM acceptance_criteria")
    needle = slugify(practice_area)
    for row in all_rows:
        if slugify(str(row.get("practice_area") or "")) == needle and isinstance(
            row.get("payload"), dict
        ):
            return row["payload"]
    return None


def match_practice_area(case_type: str) -> str | None:
    """Map free-text case_type to a KB practice area name (deterministic)."""
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
        return PRACTICE_AREA_ALIASES[needle]

    for area in areas:
        area_slug = slugify(area)
        if needle in area_slug or area_slug in needle:
            return area

    best: tuple[int, str] | None = None
    needle_tokens = set(needle.split("_"))
    for area in areas:
        tokens = set(slugify(area).split("_"))
        score = len(needle_tokens & tokens)
        if score and (best is None or score > best[0]):
            best = (score, area)
    return best[1] if best else None


def parse_sol_duration_days(rule_text: str) -> tuple[int | None, bool]:
    """
    Parse a duration in days from SOL rule text.

    Returns (days, open_ended). open_ended=True means no filing SOL (e.g. divorce).
    """
    if not rule_text:
        return None, False
    if _NO_SOL_RE.search(rule_text):
        return None, True

    years = _YEARS_RE.search(rule_text)
    if years:
        return int(float(years.group(1)) * 365), False

    months = _MONTHS_RE.search(rule_text)
    if months:
        return int(float(months.group(1)) * 30), False

    days = _DAYS_RE.search(rule_text)
    if days:
        return int(float(days.group(1))), False

    return None, False


def lookup_sol_rule(practice_area: str, jurisdiction: str) -> str | None:
    """Lookup SOL rule text from Postgres sol_rules (seeded from kb/sol_tables.json)."""
    jur = jurisdiction.strip().upper()
    rows = query_structured(
        """
        SELECT rule_text
        FROM sol_rules
        WHERE practice_area = :area AND jurisdiction = :jur
        LIMIT 1
        """,
        {"area": practice_area, "jur": jur},
    )
    if rows:
        return str(rows[0].get("rule_text") or "") or None

    all_rows = query_structured(
        "SELECT practice_area, jurisdiction, rule_text FROM sol_rules WHERE jurisdiction = :jur",
        {"jur": jur},
    )
    needle = slugify(practice_area)
    for row in all_rows:
        if slugify(str(row.get("practice_area") or "")) == needle:
            return str(row.get("rule_text") or "") or None
    return None


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
