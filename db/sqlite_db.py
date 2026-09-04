"""SQLite structured database: Alembic schema + SQLAlchemy seed."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.engine import DEFAULT_DB_PATH, get_engine, session_scope, sqlite_url
from db.models import Attorney, Client, PastCase

KB_DIR = ROOT / "kb"
ALEMBIC_INI = Path(__file__).resolve().parent / "alembic.ini"
HEAD_REVISION = "001_initial"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a sqlite3 connection for tools that still use raw SQL."""
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _alembic_config(db_path: Path):
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", sqlite_url(db_path))
    return cfg


def _current_revision(engine: Engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as connection:
        row = connection.exec_driver_sql("SELECT version_num FROM alembic_version").fetchone()
    return str(row[0]) if row else None


def _has_legacy_tables(engine: Engine) -> bool:
    tables = set(inspect(engine).get_table_names())
    return {"clients", "attorneys", "past_cases"}.issubset(tables)


def upgrade_schema(*, db_path: Path | str | None = None) -> None:
    """Apply Alembic migrations. Stamp existing pre-Alembic databases at head."""
    from alembic import command
    from alembic.script import ScriptDirectory

    path = Path(db_path or DEFAULT_DB_PATH)
    engine = get_engine(path)
    cfg = _alembic_config(path)
    head = ScriptDirectory.from_config(cfg).get_current_head()
    revision = _current_revision(engine)
    if revision == head:
        return
    if revision is None and _has_legacy_tables(engine):
        command.stamp(cfg, head or HEAD_REVISION)
        return
    command.upgrade(cfg, "head")


def init_schema(
    conn: sqlite3.Connection | None = None,
    *,
    db_path: Path | str | None = None,
) -> sqlite3.Connection:
    """Create or migrate structured tables, then return a sqlite3 connection."""
    path = Path(db_path or DEFAULT_DB_PATH)
    upgrade_schema(db_path=path)
    if conn is not None:
        return conn
    return connect(path)


def _slug(value: str) -> str:
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_")


def _attorney_id(name: str, practice_area: str) -> str:
    return f"att-{_slug(practice_area)}-{_slug(name)}"


def _case_id(practice_area: str, title: str, index: int) -> str:
    return f"case-{_slug(practice_area)}-{index + 1:03d}-{_slug(title)[:40]}"


def _read_kb_json(filename: str) -> dict[str, Any]:
    path = KB_DIR / filename
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _upsert(session, model, row: dict[str, Any], update_fields: tuple[str, ...]) -> None:
    stmt = insert(model).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={field: stmt.excluded[field] for field in update_fields},
    )
    session.execute(stmt)


def upsert_client(session, row: dict[str, Any]) -> None:
    _upsert(session, Client, row, ("name", "email", "phone", "state"))


def upsert_attorney(session, row: dict[str, Any]) -> None:
    _upsert(
        session,
        Attorney,
        row,
        ("name", "specialization", "experience_years", "jurisdictions", "availability"),
    )


def upsert_past_case(session, row: dict[str, Any]) -> None:
    _upsert(
        session,
        PastCase,
        row,
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


def seed_from_kb(conn: Any | None = None, *, db_path: Path | str | None = None) -> dict[str, int]:
    """
    Idempotent seed from kb/*.json into structured tables.

    Links past_cases to attorneys/clients in the same practice area by index
    when both exist. `conn` is accepted for compatibility and ignored.
    """
    del conn
    path = Path(db_path or DEFAULT_DB_PATH)
    upgrade_schema(db_path=path)

    clients_by_area = _read_kb_json("clients.json")
    attorneys_by_area = _read_kb_json("attorneys.json")
    cases_by_area = _read_kb_json("past_cases.json")

    client_counts = 0
    attorney_counts = 0
    case_counts = 0
    attorney_ids: dict[str, list[str]] = {}
    client_ids: dict[str, list[str]] = {}

    with session_scope(path) as session:
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
                    "jurisdictions": json.dumps(attorney.get("jurisdictions") or [], ensure_ascii=False),
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
                    "attorney_id": att_list[index] if index < len(att_list) else (att_list[0] if att_list else None),
                    "client_id": cli_list[index] if index < len(cli_list) else (cli_list[0] if cli_list else None),
                }
                upsert_past_case(session, row)
                case_counts += 1

    return {
        "clients": client_counts,
        "attorneys": attorney_counts,
        "past_cases": case_counts,
    }


def table_counts(*, db_path: Path | str | None = None) -> dict[str, int]:
    with session_scope(db_path) as session:
        return {
            "clients": session.scalar(select(func.count()).select_from(Client)) or 0,
            "attorneys": session.scalar(select(func.count()).select_from(Attorney)) or 0,
            "past_cases": session.scalar(select(func.count()).select_from(PastCase)) or 0,
        }


def init_db(*, db_path: Path | str | None = None, seed: bool = True) -> dict[str, Any]:
    """Migrate schema and optionally seed from the knowledge base."""
    path = Path(db_path or DEFAULT_DB_PATH)
    upgrade_schema(db_path=path)
    seeded = seed_from_kb(db_path=path) if seed else {"clients": 0, "attorneys": 0, "past_cases": 0}
    counts = table_counts(db_path=path)
    return {"db_path": str(path), "seeded": seeded, "counts": counts}


if __name__ == "__main__":
    result = init_db(seed=True)
    print(f"SQLite ready at {result['db_path']}")
    print(f"seeded={result['seeded']}")
    print(f"counts={result['counts']}")
