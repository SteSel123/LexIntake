"""Shared helpers for LexIntake Agno tools."""

from __future__ import annotations

import json
import re
import sys
import time as _time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "kb"
DB_DIR = ROOT / "db"
ETL_DIR = ROOT / "etl"

for path in (str(ROOT), str(DB_DIR), str(ETL_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from monitoring.app_logging import get_console_logger  # noqa: E402

logger = get_console_logger("tools")

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*years?", re.I)
_MONTHS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*months?", re.I)
_DAYS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*days?", re.I)
_NO_SOL_RE = re.compile(r"\bno\s+sol\b|\bno\s+single\s+sol\b", re.I)


def slugify(value: str | None) -> str:
    if not value:
        return ""
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_")


@lru_cache(maxsize=16)
def load_kb_json(filename: str) -> Any:
    path = KB_DIR / filename
    if not path.exists():
        logger.error("KB file missing: %s", path)
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read KB file %s: %s", path, exc)
        return None


def load_practice_areas() -> list[str]:
    data = load_kb_json("practice_areas.json")
    return list(data) if isinstance(data, list) else []


def match_practice_area(case_type: str) -> str | None:
    """Map free-text case_type to a KB practice area name (deterministic)."""
    if not case_type:
        return None
    areas = load_practice_areas()
    needle = slugify(case_type)
    if not needle:
        return None

    # Exact slug match
    for area in areas:
        if slugify(area) == needle:
            return area

    # Alias / containment match
    aliases = {
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
    if needle in aliases:
        return aliases[needle]

    for area in areas:
        area_slug = slugify(area)
        if needle in area_slug or area_slug in needle:
            return area

    # Token overlap score
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
    tables = load_kb_json("sol_tables.json")
    if not isinstance(tables, dict):
        return None
    area_rules = tables.get(practice_area)
    if not isinstance(area_rules, dict):
        # try fuzzy area key
        for key, value in tables.items():
            if slugify(key) == slugify(practice_area):
                area_rules = value
                break
    if not isinstance(area_rules, dict):
        return None
    jur = jurisdiction.strip().upper()
    if jur in area_rules:
        return str(area_rules[jur])
    for key, value in area_rules.items():
        if slugify(key) == slugify(jur):
            return str(value)
    return None


def get_sqlite_connection():
    try:
        from sqlite_db import connect, init_schema

        conn = connect()
        init_schema(conn)
        return conn
    except Exception as exc:  # noqa: BLE001
        logger.error("SQLite connection failed: %s", exc)
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
    """Search LanceDB kb_docs; returns [] on any failure."""
    try:
        from etl.transform.embeddings import get_embedder
        from lancedb_store import ensure_kb_docs, search_kb_docs

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
                table = ensure_kb_docs(dimensions=len(vector))
                total = int(table.count_rows())
                from monitoring.logger import log_retrieval

                log_retrieval(query, hits=len(hits), total_chunks=total)
            except Exception:  # noqa: BLE001
                pass
        return hits
    except Exception as exc:  # noqa: BLE001
        logger.error("Vector search failed: %s", exc)
        if log:
            try:
                from monitoring.logger import log_retrieval

                log_retrieval(query, hits=0, total_chunks=0)
            except Exception:  # noqa: BLE001
                pass
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
        except Exception:  # noqa: BLE001
            pass
