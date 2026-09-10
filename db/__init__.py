"""LexIntake database package: PostgreSQL entities + pgvector kb_docs.

Public surface re-exports structured-table helpers (Alembic init, seeding,
raw SQL queries) and vector-store operations used by RAG tools and ETL.
"""

from .pgvector_store import (
    count_rows as count_kb_docs,
    ensure_kb_docs,
    existing_by_id,
    fuzzy_text_search,
    search_kb_docs,
    upsert_kb_docs,
)
from .schema import COLLECTION_NAME, DEFAULT_EMBEDDING_DIMS
from .structured_db import init_db, init_schema, query_rows, seed_from_kb

__all__ = [
    "COLLECTION_NAME",
    "DEFAULT_EMBEDDING_DIMS",
    "count_kb_docs",
    "ensure_kb_docs",
    "existing_by_id",
    "fuzzy_text_search",
    "init_db",
    "init_schema",
    "query_rows",
    "search_kb_docs",
    "seed_from_kb",
    "upsert_kb_docs",
]
