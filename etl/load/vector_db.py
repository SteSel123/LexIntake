"""Load embedded chunks into PostgreSQL kb_docs (pgvector).

Load properties:
- Re-runnable: safe to execute repeatedly
- Idempotent: upsert by chunk_id (no duplicates)
- Incremental: new/changed chunks upserted; existing rows retained
"""

from __future__ import annotations

from typing import Any

from db.pgvector_store import ensure_kb_docs
from db.pgvector_store import existing_by_id as pg_existing_by_id
from db.pgvector_store import upsert_kb_docs
from etl.transform.embeddings import DEFAULT_DIMENSIONS


def existing_by_id() -> dict[str, dict[str, Any]]:
    """Return previously persisted records keyed by chunk_id (for incremental embed)."""
    return pg_existing_by_id()


def load(
    records: list[dict[str, Any]],
    *,
    dimensions: int | None = None,
    recreate_on_dim_mismatch: bool = False,
) -> dict[str, Any]:
    """Persist embedded chunks to PostgreSQL kb_docs."""
    dims = dimensions or DEFAULT_DIMENSIONS
    ensure_kb_docs(dimensions=dims, recreate_on_dim_mismatch=recreate_on_dim_mismatch)
    stats = upsert_kb_docs(records, dimensions=dims)
    return {
        "backend": "postgres",
        "pg_stats": stats,
    }
