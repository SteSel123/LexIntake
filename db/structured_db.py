"""Structured PostgreSQL database: Alembic schema + seed from kb/.

Applies migrations to head, loads JSON fixtures from ``kb/`` into relational
tables, and exposes ``query_rows`` for Agno tools that need ad-hoc SQL reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from db.engine import database_url, get_engine, session_scope
from db.models import (
    AcceptanceCriteria,
    Attorney,
    Client,
    PastCase,
    PracticeArea,
    SolRule,
)
from tools.common import slugify

ROOT = Path(__file__).resolve().parent.parent

# Paths and revision id used to detect whether Alembic upgrade is needed.
KB_DIR = ROOT / "kb"
ALEMBIC_INI = Path(__file__).resolve().parent / "alembic.ini"
HEAD_REVISION = "003_kb_ref"


# --- Public read API -------------------------------------------------------


def query_rows(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Read helper used by Agno tools.

    Ensures schema is at head before executing parameterized raw SQL and
    returning rows as plain dicts (no ORM objects).
    """
    upgrade_schema()
    with session_scope() as session:
        result = session.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings()]


# --- Alembic migration helpers ---------------------------------------------


def _alembic_config():
    """Build Alembic Config pointing at this package's migrations and DATABASE_URL."""
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))
    return cfg


def _current_revision(engine: Engine) -> str | None:
    """Return stamped Alembic revision, or ``None`` if ``alembic_version`` is absent."""
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as connection:
        row = connection.exec_driver_sql("SELECT version_num FROM alembic_version").fetchone()
    return str(row[0]) if row else None


def upgrade_schema() -> None:
    """Apply Alembic migrations to head."""
    from alembic import command
    from alembic.script import ScriptDirectory

    engine = get_engine()
    cfg = _alembic_config()
    head = ScriptDirectory.from_config(cfg).get_current_head()
    revision = _current_revision(engine)
    if revision == head:
        return
    command.upgrade(cfg, "head")


def init_schema() -> None:
    """Create or migrate structured + KB tables."""
    upgrade_schema()


# --- Deterministic id helpers for kb/ seed rows ----------------------------


def _attorney_id(name: str, practice_area: str) -> str:
    """Stable attorney primary key derived from name and practice area slug."""
    return f"att-{slugify(practice_area)}-{slugify(name)}"


def _case_id(practice_area: str, title: str, index: int) -> str:
    """Stable past-case id: practice area, ordinal, and truncated title slug."""
    return f"case-{slugify(practice_area)}-{index + 1:03d}-{slugify(title)[:40]}"


def _sol_rule_id(practice_area: str, jurisdiction: str) -> str:
    """Stable SOL rule id from practice area and jurisdiction slugs."""
    return f"sol-{slugify(practice_area)}-{slugify(jurisdiction)}"


def _read_kb_json(filename: str) -> Any:
    """Load one JSON fixture from ``kb/`` (raises if missing)."""
    path = KB_DIR / filename
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# --- PostgreSQL upsert helpers (idempotent seed) ---------------------------


def _upsert(session, model, row: dict[str, Any], pk: str, update_fields: tuple[str, ...]) -> None:
    """INSERT … ON CONFLICT DO UPDATE for one ORM model row."""
    stmt = pg_insert(model).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[pk],
        set_={field: stmt.excluded[field] for field in update_fields},
    )
    session.execute(stmt)


def upsert_client(session, row: dict[str, Any]) -> None:
    """Upsert a ``clients`` row by primary key ``id``."""
    _upsert(session, Client, row, "id", ("name", "email", "phone", "state"))


def upsert_attorney(session, row: dict[str, Any]) -> None:
    """Upsert an ``attorneys`` row by primary key ``id``."""
    _upsert(
        session,
        Attorney,
        row,
        "id",
        ("name", "specialization", "experience_years", "jurisdictions", "availability"),
    )


def upsert_past_case(session, row: dict[str, Any]) -> None:
    """Upsert a ``past_cases`` row by primary key ``id``."""
    _upsert(
        session,
        PastCase,
        row,
        "id",
        (
            "title",
            "practice_area",
            "jurisdiction",
            "facts",
            "outcome",
            "settlement_amount",
            "attorney_id",
            "client_id",
        ),
    )


def upsert_practice_area(session, name: str) -> None:
    """Insert practice area name if not already present."""
    stmt = pg_insert(PracticeArea).values(name=name)
    stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
    session.execute(stmt)


def upsert_sol_rule(session, row: dict[str, Any]) -> None:
    """Upsert a ``sol_rules`` row by primary key ``id``."""
    _upsert(
        session,
        SolRule,
        row,
        "id",
        ("practice_area", "jurisdiction", "rule_text"),
    )


def upsert_acceptance_criteria(session, practice_area: str, payload: dict[str, Any]) -> None:
    """Upsert JSON acceptance criteria for one practice area."""
    _upsert(
        session,
        AcceptanceCriteria,
        {"practice_area": practice_area, "payload": payload},
        "practice_area",
        ("payload",),
    )


# --- Seed orchestration ----------------------------------------------------


def seed_from_kb() -> dict[str, int]:
    """Idempotent seed from kb/*.json into structured tables.

    Re-running updates existing rows via upsert; returns per-table insert counts
    for CLI reporting (counts reflect loop iterations, not net new rows).
    """
    upgrade_schema()

    practice_areas = _read_kb_json("practice_areas.json")
    sol_tables = _read_kb_json("sol_tables.json")
    acceptance = _read_kb_json("acceptance_criteria.json")
    clients_by_area = _read_kb_json("clients.json")
    attorneys_by_area = _read_kb_json("attorneys.json")
    cases_by_area = _read_kb_json("past_cases.json")

    practice_area_counts = 0
    sol_rule_counts = 0
    acceptance_counts = 0
    client_counts = 0
    attorney_counts = 0
    case_counts = 0
    attorney_ids: dict[str, list[str]] = {}
    client_ids: dict[str, list[str]] = {}

    with session_scope() as session:
        if isinstance(practice_areas, list):
            for name in practice_areas:
                if isinstance(name, str) and name.strip():
                    upsert_practice_area(session, name.strip())
                    practice_area_counts += 1

        if isinstance(sol_tables, dict):
            for practice_area, rules in sol_tables.items():
                if not isinstance(rules, dict):
                    continue
                for jurisdiction, rule_text in rules.items():
                    row = {
                        "id": _sol_rule_id(str(practice_area), str(jurisdiction)),
                        "practice_area": str(practice_area),
                        "jurisdiction": str(jurisdiction).strip().upper(),
                        "rule_text": str(rule_text),
                    }
                    upsert_sol_rule(session, row)
                    sol_rule_counts += 1

        if isinstance(acceptance, dict):
            for practice_area, payload in acceptance.items():
                if isinstance(payload, dict):
                    upsert_acceptance_criteria(session, str(practice_area), payload)
                    acceptance_counts += 1

        for practice_area, clients in clients_by_area.items():
            client_ids[practice_area] = []
            for client in clients:
                row = {
                    "id": client["id"],
                    "name": client["name"],
                    "email": client.get("email"),
                    "phone": client.get("phone"),
                    "state": client.get("jurisdiction") or client.get("state"),
                }
                upsert_client(session, row)
                client_ids[practice_area].append(row["id"])
                client_counts += 1

        for practice_area, attorneys in attorneys_by_area.items():
            attorney_ids[practice_area] = []
            for attorney in attorneys:
                row = {
                    "id": _attorney_id(attorney["name"], practice_area),
                    "name": attorney["name"],
                    "specialization": attorney["specialization"],
                    "experience_years": attorney.get("experience_years"),
                    "jurisdictions": json.dumps(
                        attorney.get("jurisdictions") or [], ensure_ascii=False
                    ),
                    "availability": attorney.get("availability"),
                }
                upsert_attorney(session, row)
                attorney_ids[practice_area].append(row["id"])
                attorney_counts += 1

        for practice_area, cases in cases_by_area.items():
            for index, case in enumerate(cases):
                att_list = attorney_ids.get(practice_area) or []
                cli_list = client_ids.get(practice_area) or []
                row = {
                    "id": _case_id(practice_area, case["title"], index),
                    "title": case["title"],
                    "practice_area": practice_area,
                    "jurisdiction": case["jurisdiction"],
                    "facts": case["facts"],
                    "outcome": case.get("outcome"),
                    "settlement_amount": case.get("settlement_or_award_usd"),
                    "attorney_id": att_list[index]
                    if index < len(att_list)
                    else (att_list[0] if att_list else None),
                    "client_id": cli_list[index]
                    if index < len(cli_list)
                    else (cli_list[0] if cli_list else None),
                }
                upsert_past_case(session, row)
                case_counts += 1

    return {
        "practice_areas": practice_area_counts,
        "sol_rules": sol_rule_counts,
        "acceptance_criteria": acceptance_counts,
        "clients": client_counts,
        "attorneys": attorney_counts,
        "past_cases": case_counts,
    }


def table_counts() -> dict[str, int]:
    """Return row counts for all structured seed tables."""
    with session_scope() as session:
        return {
            "practice_areas": session.scalar(select(func.count()).select_from(PracticeArea)) or 0,
            "sol_rules": session.scalar(select(func.count()).select_from(SolRule)) or 0,
            "acceptance_criteria": session.scalar(
                select(func.count()).select_from(AcceptanceCriteria)
            )
            or 0,
            "clients": session.scalar(select(func.count()).select_from(Client)) or 0,
            "attorneys": session.scalar(select(func.count()).select_from(Attorney)) or 0,
            "past_cases": session.scalar(select(func.count()).select_from(PastCase)) or 0,
        }


def init_db(*, seed: bool = True) -> dict[str, Any]:
    """Migrate schema and optionally seed from the knowledge base.

    Returns connection metadata, seed summary, and post-seed table counts for
    operational logging and health checks.
    """
    upgrade_schema()
    seeded = (
        seed_from_kb()
        if seed
        else {
            "practice_areas": 0,
            "sol_rules": 0,
            "acceptance_criteria": 0,
            "clients": 0,
            "attorneys": 0,
            "past_cases": 0,
        }
    )
    counts = table_counts()
    return {
        "database_url": database_url(),
        "dialect": "postgresql",
        "seeded": seeded,
        "counts": counts,
    }


# CLI entry when run as ``python -m db.structured_db``.
if __name__ == "__main__":
    result = init_db(seed=True)
    print("PostgreSQL ready")
    print(f"url={result['database_url']}")
    print(f"seeded={result['seeded']}")
    print(f"counts={result['counts']}")
