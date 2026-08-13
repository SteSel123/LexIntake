"""SQLite structured database for LexIntake entities."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(
    os.getenv("LEXINTAKE_SQLITE_PATH", ROOT / "db" / "lexintake.db")
)
SCHEMA_PATH = Path(__file__).resolve().parent / "sql" / "schema.sql"
KB_DIR = ROOT / "kb"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open SQLite connection with foreign keys enabled."""
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection | None = None, *, db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create clients, attorneys, and past_cases tables if they do not exist."""
    owns_connection = conn is None
    connection = conn or connect(db_path)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema_sql)
    connection.commit()
    if owns_connection:
        return connection
    return connection


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


def upsert_client(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO clients (id, name, email, phone, state)
        VALUES (:id, :name, :email, :phone, :state)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            email = excluded.email,
            phone = excluded.phone,
            state = excluded.state
        """,
        row,
    )


def upsert_attorney(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO attorneys (
            id, name, specialization, experience_years, jurisdictions, availability
        )
        VALUES (
            :id, :name, :specialization, :experience_years, :jurisdictions, :availability
        )
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            specialization = excluded.specialization,
            experience_years = excluded.experience_years,
            jurisdictions = excluded.jurisdictions,
            availability = excluded.availability
        """,
        row,
    )


def upsert_past_case(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO past_cases (
            id, title, practice_area, jurisdiction, facts, outcome,
            settlement_amount, attorney_id, client_id
        )
        VALUES (
            :id, :title, :practice_area, :jurisdiction, :facts, :outcome,
            :settlement_amount, :attorney_id, :client_id
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            practice_area = excluded.practice_area,
            jurisdiction = excluded.jurisdiction,
            facts = excluded.facts,
            outcome = excluded.outcome,
            settlement_amount = excluded.settlement_amount,
            attorney_id = excluded.attorney_id,
            client_id = excluded.client_id
        """,
        row,
    )


def seed_from_kb(conn: sqlite3.Connection | None = None, *, db_path: Path | str | None = None) -> dict[str, int]:
    """
    Idempotent seed from kb/*.json into structured tables.

    Links past_cases to attorneys/clients in the same practice area by index
    when both exist.
    """
    owns_connection = conn is None
    connection = conn or init_schema(db_path=db_path)

    clients_by_area = _read_kb_json("clients.json")
    attorneys_by_area = _read_kb_json("attorneys.json")
    cases_by_area = _read_kb_json("past_cases.json")

    client_counts = 0
    attorney_counts = 0
    case_counts = 0

    attorney_ids: dict[str, list[str]] = {}
    client_ids: dict[str, list[str]] = {}

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
            upsert_client(connection, row)
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
            upsert_attorney(connection, row)
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
            upsert_past_case(connection, row)
            case_counts += 1

    connection.commit()
    if owns_connection:
        connection.close()

    return {
        "clients": client_counts,
        "attorneys": attorney_counts,
        "past_cases": case_counts,
    }


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("clients", "attorneys", "past_cases"):
        counts[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    return counts


def init_db(*, db_path: Path | str | None = None, seed: bool = True) -> dict[str, Any]:
    """Initialize schema and optionally seed from the knowledge base."""
    conn = init_schema(db_path=db_path)
    seeded = seed_from_kb(conn) if seed else {"clients": 0, "attorneys": 0, "past_cases": 0}
    counts = table_counts(conn)
    path = Path(db_path or DEFAULT_DB_PATH)
    conn.close()
    return {"db_path": str(path), "seeded": seeded, "counts": counts}


if __name__ == "__main__":
    result = init_db(seed=True)
    print(f"SQLite ready at {result['db_path']}")
    print(f"seeded={result['seeded']}")
    print(f"counts={result['counts']}")
