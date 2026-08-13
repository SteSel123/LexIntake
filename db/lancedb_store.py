"""LanceDB initialization, kb_docs collection management, and upserts."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

import lancedb
import pyarrow as pa

try:
    from schema import (
        COLLECTION_NAME,
        DEFAULT_EMBEDDING_DIMS,
        empty_kb_docs_table,
        kb_docs_schema,
    )
except ImportError:  # pragma: no cover - package import path
    from .schema import (
        COLLECTION_NAME,
        DEFAULT_EMBEDDING_DIMS,
        empty_kb_docs_table,
        kb_docs_schema,
    )

DEFAULT_DB_DIR = Path(__file__).resolve().parent / "lancedb"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def connect(db_dir: Path | str | None = None) -> lancedb.DBConnection:
    """Initialize / open the local LanceDB database."""
    path = Path(db_dir or os.getenv("LEXINTAKE_LANCEDB_DIR", DEFAULT_DB_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(path))


def slugify_practice_area(value: str | None) -> str:
    """Normalize practice area labels to stable snake_case keys."""
    if not value:
        return ""
    slug = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    return slug


def normalize_doc_type(value: str | None) -> str:
    """Keep doc_type machine-readable and stable."""
    if not value:
        return ""
    return slugify_practice_area(value)


def ensure_kb_docs(
    db: lancedb.DBConnection | None = None,
    *,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
    db_dir: Path | str | None = None,
    recreate_on_dim_mismatch: bool = True,
) -> Any:
    """
    Create the kb_docs collection if missing; open it otherwise.

    Returns the LanceDB table handle.
    """
    connection = db or connect(db_dir)
    listed = connection.list_tables()
    names = set(getattr(listed, "tables", listed) or [])
    if COLLECTION_NAME in names:
        table = connection.open_table(COLLECTION_NAME)
        if recreate_on_dim_mismatch:
            try:
                schema = table.schema
                # fixed_size_list<item: float>[N]
                emb = schema.field("embedding").type
                existing_dims = getattr(emb, "list_size", None)
                if existing_dims and int(existing_dims) != int(dimensions):
                    connection.drop_table(COLLECTION_NAME)
                    names.discard(COLLECTION_NAME)
                else:
                    return table
            except Exception:
                return table
        else:
            return table

    if COLLECTION_NAME not in names:
        table = connection.create_table(
            COLLECTION_NAME,
            data=empty_kb_docs_table(dimensions),
            schema=kb_docs_schema(dimensions),
            mode="create",
        )
        return table
    return connection.open_table(COLLECTION_NAME)

def _as_float32_vector(values: Iterable[float], dimensions: int) -> list[float]:
    vector = [float(v) for v in values]
    if len(vector) != dimensions:
        raise ValueError(
            f"embedding length {len(vector)} does not match schema dimensions {dimensions}"
        )
    return vector


def records_to_arrow(
    records: list[dict[str, Any]],
    *,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
) -> pa.Table:
    """Convert ETL chunk records into a typed Arrow table for kb_docs."""
    # Last write wins for duplicate chunk_ids in one batch (idempotent input).
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        chunk_id = record.get("chunk_id")
        if not chunk_id:
            continue
        by_id[str(chunk_id)] = record

    rows: list[dict[str, Any]] = []
    for chunk_id in sorted(by_id):
        record = by_id[chunk_id]
        meta = record.get("metadata") or {}
        practice_area = meta.get("practice_area", record.get("practice_area"))
        doc_type = meta.get("doc_type", record.get("doc_type"))
        jurisdictions = meta.get("jurisdictions") or []
        if not isinstance(jurisdictions, list):
            jurisdictions = [str(jurisdictions)]

        rows.append(
            {
                "chunk_id": chunk_id,
                "text": str(record.get("text") or ""),
                "embedding": _as_float32_vector(record.get("embedding") or [], dimensions),
                "metadata": {
                    "practice_area": slugify_practice_area(
                        practice_area if practice_area is None else str(practice_area)
                    ),
                    "jurisdictions": [str(j) for j in jurisdictions],
                    "doc_type": normalize_doc_type(
                        doc_type if doc_type is None else str(doc_type)
                    ),
                },
            }
        )

    schema = kb_docs_schema(dimensions)
    if not rows:
        return pa.Table.from_pylist([], schema=schema)
    return pa.Table.from_pylist(rows, schema=schema)


def upsert_kb_docs(
    records: list[dict[str, Any]],
    *,
    db: lancedb.DBConnection | None = None,
    table: Any | None = None,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
    db_dir: Path | str | None = None,
) -> dict[str, int]:
    """
    Upsert ETL chunks into kb_docs using chunk_id as the primary key.

    Properties:
    - repeatable: same chunk payload overwrites the same row
    - idempotent: merge_insert on chunk_id prevents duplicate keys
    - incremental: existing rows not present in this batch are retained
      (no delete-missing / full replace)
    """
    connection = db or connect(db_dir)
    target = table or ensure_kb_docs(connection, dimensions=dimensions, db_dir=db_dir)
    arrow = records_to_arrow(records, dimensions=dimensions)

    if arrow.num_rows == 0:
        return {"received": 0, "inserted": 0, "updated": 0, "deleted": 0, "total": target.count_rows()}

    result = (
        target.merge_insert("chunk_id")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute(arrow)
    )

    return {
        "received": arrow.num_rows,
        "inserted": int(getattr(result, "num_inserted_rows", 0) or 0),
        "updated": int(getattr(result, "num_updated_rows", 0) or 0),
        "deleted": int(getattr(result, "num_deleted_rows", 0) or 0),
        "total": target.count_rows(),
    }


def existing_by_id(
    *,
    db: lancedb.DBConnection | None = None,
    table: Any | None = None,
    db_dir: Path | str | None = None,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
) -> dict[str, dict[str, Any]]:
    """Return chunk_id -> record map for incremental embedding reuse."""
    connection = db or connect(db_dir)
    listed = connection.list_tables()
    names = set(getattr(listed, "tables", listed) or [])
    if COLLECTION_NAME not in names:
        return {}

    target = table or connection.open_table(COLLECTION_NAME)
    arrow = target.to_arrow()
    out: dict[str, dict[str, Any]] = {}

    for row in arrow.to_pylist():
        chunk_id = row.get("chunk_id")
        if not chunk_id:
            continue
        meta = row.get("metadata") or {}
        out[str(chunk_id)] = {
            "chunk_id": chunk_id,
            "text": row.get("text"),
            "embedding": row.get("embedding"),
            "embedding_dimensions": dimensions,
            "metadata": {
                "practice_area": meta.get("practice_area"),
                "jurisdictions": meta.get("jurisdictions") or [],
                "doc_type": meta.get("doc_type"),
                # content_hash is not stored in kb_docs; force re-embed unless caller adds it
                "content_hash": None,
            },
        }
    return out


def search_kb_docs(
    query_embedding: list[float],
    *,
    top_k: int = 5,
    practice_area: str | None = None,
    jurisdiction: str | None = None,
    doc_type: str | None = None,
    db_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Vector search over kb_docs with optional metadata filters."""
    table = ensure_kb_docs(db_dir=db_dir, dimensions=len(query_embedding))
    # Over-fetch when post-filtering by jurisdiction / doc_type
    fetch_k = top_k * 4 if (jurisdiction or doc_type) else top_k
    query = table.search(query_embedding).limit(fetch_k)
    if practice_area:
        slug = slugify_practice_area(practice_area)
        query = query.where(f"metadata.practice_area = '{slug}'")
    if doc_type:
        dtype = normalize_doc_type(doc_type)
        query = query.where(f"metadata.doc_type = '{dtype}'")

    rows = query.to_list()
    if jurisdiction:
        jur = str(jurisdiction).strip().upper()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            meta = row.get("metadata") or {}
            jurisdictions = meta.get("jurisdictions") or []
            # Also accept jurisdiction tokens inside text for SOL tables
            text = str(row.get("text") or "")
            if jur in [str(j).upper() for j in jurisdictions] or f'"{jur}"' in text or f"{jur}:" in text:
                filtered.append(row)
        rows = filtered or rows
    return rows[:top_k]


if __name__ == "__main__":
    db = connect()
    table = ensure_kb_docs(db)
    print(f"LanceDB ready at {DEFAULT_DB_DIR}")
    print(f"collection={COLLECTION_NAME} rows={table.count_rows()}")
    print(table.schema)
