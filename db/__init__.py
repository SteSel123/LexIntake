"""LexIntake database package: LanceDB (vectors) + SQLite (entities)."""

from .lancedb_store import connect as connect_lancedb
from .lancedb_store import ensure_kb_docs, upsert_kb_docs
from .schema import COLLECTION_NAME, kb_docs_schema
from .sqlite_db import connect as connect_sqlite
from .sqlite_db import init_db, init_schema, seed_from_kb

__all__ = [
    "COLLECTION_NAME",
    "connect_lancedb",
    "connect_sqlite",
    "ensure_kb_docs",
    "init_db",
    "init_schema",
    "kb_docs_schema",
    "seed_from_kb",
    "upsert_kb_docs",
]
