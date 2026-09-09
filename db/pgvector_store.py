"""PostgreSQL + pgvector store for heterogeneous KB chunks (kb_docs)."""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import EMBED_DIMS, EMBED_MODEL
from db.engine import ensure_postgres_extensions, get_engine
from db.schema import DEFAULT_EMBEDDING_DIMS
from tools.common import slugify

COLLECTION_NAME = "kb_docs"


def slugify_practice_area(value: str | None) -> str:
    return slugify(value)


def normalize_doc_type(value: str | None) -> str:
    return slugify(value)


def _as_float_vector(values: Iterable[float], dimensions: int) -> list[float]:
    vector = [float(v) for v in values]
    if len(vector) != dimensions:
        raise ValueError(
            f"embedding length {len(vector)} does not match schema dimensions {dimensions}"
        )
    return vector


def _vector_literal(vector: list[float]) -> str:
    # pgvector accepts '[1,2,3]'::vector
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def ensure_kb_docs(
    engine: Engine | None = None,
    *,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
    recreate_on_dim_mismatch: bool = True,
) -> Engine:
    """
    Ensure Postgres extensions + kb_docs table exist.

    Returns the SQLAlchemy engine (kb_docs is ensured as a side effect).
    """
    eng = engine or get_engine()
    ensure_postgres_extensions(eng)
    dims = int(dimensions or EMBED_DIMS or DEFAULT_EMBEDDING_DIMS)

    with eng.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'kb_docs'"
            )
        ).scalar()
        if exists and recreate_on_dim_mismatch:
            current = conn.execute(
                text(
                    """
                    SELECT atttypmod
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    JOIN pg_namespace n ON c.relnamespace = n.oid
                    WHERE n.nspname = 'public'
                      AND c.relname = 'kb_docs'
                      AND a.attname = 'embedding'
                      AND NOT a.attisdropped
                    """
                )
            ).scalar()
            # atttypmod for vector(N) is N+4 in pgvector
            if current is not None and int(current) - 4 != dims:
                conn.execute(text("DROP TABLE IF EXISTS kb_docs CASCADE"))
                exists = None

        if not exists:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE kb_docs (
                        chunk_id TEXT PRIMARY KEY,
                        text TEXT NOT NULL,
                        embedding vector({dims}) NOT NULL,
                        doc_type TEXT NOT NULL DEFAULT '',
                        practice_area TEXT NOT NULL DEFAULT '',
                        jurisdictions TEXT[] NOT NULL DEFAULT '{{}}',
                        content_hash TEXT,
                        embedding_model TEXT,
                        embedding_dimensions INTEGER,
                        payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_kb_docs_embedding_hnsw
                    ON kb_docs USING hnsw (embedding vector_cosine_ops)
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_kb_docs_doc_type ON kb_docs (doc_type)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_kb_docs_practice_area "
                    "ON kb_docs (practice_area)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_kb_docs_jurisdictions "
                    "ON kb_docs USING gin (jurisdictions)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_kb_docs_payload "
                    "ON kb_docs USING gin (payload)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_kb_docs_text_trgm "
                    "ON kb_docs USING gin (text gin_trgm_ops)"
                )
            )
    return eng


def count_rows(engine: Engine | None = None) -> int:
    eng = engine or ensure_kb_docs()
    with eng.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM kb_docs")).scalar() or 0)


def upsert_kb_docs(
    records: list[dict[str, Any]],
    *,
    engine: Engine | None = None,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
) -> dict[str, int]:
    """Upsert ETL chunks into Postgres kb_docs by chunk_id."""
    eng = ensure_kb_docs(engine, dimensions=dimensions)
    dims = int(dimensions)

    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        chunk_id = record.get("chunk_id")
        if not chunk_id:
            continue
        by_id[str(chunk_id)] = record

    if not by_id:
        return {"received": 0, "inserted": 0, "updated": 0, "deleted": 0, "total": count_rows(eng)}

    inserted = 0
    updated = 0
    with eng.begin() as conn:
        for chunk_id, record in by_id.items():
            meta = record.get("metadata") or {}
            practice_area = meta.get("practice_area", record.get("practice_area"))
            doc_type = meta.get("doc_type", record.get("doc_type"))
            jurisdictions = meta.get("jurisdictions") or []
            if not isinstance(jurisdictions, list):
                jurisdictions = [str(jurisdictions)]
            content_hash = record.get("content_hash") or meta.get("content_hash")
            payload = {
                k: v
                for k, v in meta.items()
                if k not in {"practice_area", "jurisdictions", "doc_type", "content_hash"}
            }
            # Preserve any explicit payload from ETL
            if isinstance(record.get("payload"), dict):
                payload.update(record["payload"])

            vector = _as_float_vector(record.get("embedding") or [], dims)
            vec_lit = _vector_literal(vector)
            params = {
                "chunk_id": chunk_id,
                "text": str(record.get("text") or ""),
                "embedding": vec_lit,
                "doc_type": normalize_doc_type(
                    doc_type if doc_type is None else str(doc_type)
                ),
                "practice_area": slugify_practice_area(
                    practice_area if practice_area is None else str(practice_area)
                ),
                "jurisdictions": [str(j) for j in jurisdictions],
                "content_hash": content_hash,
                "embedding_model": record.get("embedding_model") or EMBED_MODEL,
                "embedding_dimensions": int(
                    record.get("embedding_dimensions") or dims
                ),
                "payload": json.dumps(payload, ensure_ascii=False),
            }
            result = conn.execute(
                text(
                    """
                    INSERT INTO kb_docs (
                        chunk_id, text, embedding, doc_type, practice_area,
                        jurisdictions, content_hash, embedding_model,
                        embedding_dimensions, payload, updated_at
                    ) VALUES (
                        :chunk_id, :text, CAST(:embedding AS vector), :doc_type, :practice_area,
                        :jurisdictions, :content_hash, :embedding_model,
                        :embedding_dimensions, CAST(:payload AS jsonb), now()
                    )
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        doc_type = EXCLUDED.doc_type,
                        practice_area = EXCLUDED.practice_area,
                        jurisdictions = EXCLUDED.jurisdictions,
                        content_hash = EXCLUDED.content_hash,
                        embedding_model = EXCLUDED.embedding_model,
                        embedding_dimensions = EXCLUDED.embedding_dimensions,
                        payload = EXCLUDED.payload,
                        updated_at = now()
                    RETURNING (xmax = 0) AS inserted
                    """
                ),
                params,
            )
            row = result.fetchone()
            if row and bool(row[0]):
                inserted += 1
            else:
                updated += 1

    return {
        "received": len(by_id),
        "inserted": inserted,
        "updated": updated,
        "deleted": 0,
        "total": count_rows(eng),
    }


def existing_by_id(
    *,
    engine: Engine | None = None,
    dimensions: int = DEFAULT_EMBEDDING_DIMS,
) -> dict[str, dict[str, Any]]:
    """Return chunk_id -> record map for incremental embedding reuse."""
    eng = engine or get_engine()
    with eng.connect() as conn:
        table = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'kb_docs'"
            )
        ).scalar()
        if not table:
            return {}
        rows = conn.execute(
            text(
                """
                SELECT chunk_id, text, embedding::text AS embedding,
                       doc_type, practice_area, jurisdictions, content_hash,
                       embedding_model, embedding_dimensions, payload
                FROM kb_docs
                """
            )
        ).mappings()
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            emb_raw = row["embedding"] or ""
            # '[1,2,3]' → list[float]
            emb_text = str(emb_raw).strip().lstrip("[").rstrip("]")
            embedding = [float(x) for x in emb_text.split(",") if x.strip()] if emb_text else []
            payload = row["payload"] or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            meta = {
                "practice_area": row["practice_area"],
                "jurisdictions": list(row["jurisdictions"] or []),
                "doc_type": row["doc_type"],
                "content_hash": row["content_hash"],
                **(payload if isinstance(payload, dict) else {}),
            }
            out[str(row["chunk_id"])] = {
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "embedding": embedding,
                "embedding_model": row["embedding_model"],
                "embedding_dimensions": row["embedding_dimensions"] or dimensions,
                "content_hash": row["content_hash"],
                "metadata": meta,
            }
        return out


def search_kb_docs(
    query_embedding: list[float],
    *,
    top_k: int = 5,
    practice_area: str | None = None,
    jurisdiction: str | None = None,
    doc_type: str | None = None,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Cosine-distance vector search with metadata filters."""
    eng = ensure_kb_docs(engine, dimensions=len(query_embedding), recreate_on_dim_mismatch=False)
    vec_lit = _vector_literal(_as_float_vector(query_embedding, len(query_embedding)))
    clauses = ["TRUE"]
    params: dict[str, Any] = {"embedding": vec_lit, "limit": int(top_k) * (4 if jurisdiction else 1)}

    if practice_area:
        clauses.append("practice_area = :practice_area")
        params["practice_area"] = slugify_practice_area(practice_area)
    if doc_type:
        clauses.append("doc_type = :doc_type")
        params["doc_type"] = normalize_doc_type(doc_type)
    if jurisdiction:
        # Match array membership OR SOL-style tokens in text
        clauses.append(
            "(EXISTS (SELECT 1 FROM unnest(jurisdictions) AS j WHERE upper(j) = :jur) "
            "OR text ILIKE :jur_quote OR text ILIKE :jur_colon)"
        )
        jur = str(jurisdiction).strip().upper()
        params["jur"] = jur
        params["jur_quote"] = f'%"{jur}"%'
        params["jur_colon"] = f"%{jur}:%"

    where = " AND ".join(clauses)
    sql = f"""
        SELECT chunk_id, text, doc_type, practice_area, jurisdictions, payload,
               (embedding <=> CAST(:embedding AS vector)) AS distance
        FROM kb_docs
        WHERE {where}
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """
    with eng.connect() as conn:
        rows = list(conn.execute(text(sql), params).mappings())

    hits: list[dict[str, Any]] = []
    for row in rows:
        payload = row["payload"] or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        hits.append(
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "_distance": float(row["distance"] or 0.0),
                "metadata": {
                    "practice_area": row["practice_area"],
                    "jurisdictions": list(row["jurisdictions"] or []),
                    "doc_type": row["doc_type"],
                    **(payload if isinstance(payload, dict) else {}),
                },
            }
        )
    return hits[:top_k]


def fuzzy_text_search(
    query: str,
    *,
    top_k: int = 5,
    doc_type: str | None = None,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Optional pg_trgm similarity search across heterogeneous KB text."""
    eng = ensure_kb_docs(engine, recreate_on_dim_mismatch=False)
    params: dict[str, Any] = {"query": query, "limit": top_k}
    clauses = ["text % :query"]
    if doc_type:
        clauses.append("doc_type = :doc_type")
        params["doc_type"] = normalize_doc_type(doc_type)
    where = " AND ".join(clauses)
    sql = f"""
        SELECT chunk_id, text, doc_type, practice_area, jurisdictions, payload,
               similarity(text, :query) AS score
        FROM kb_docs
        WHERE {where}
        ORDER BY score DESC
        LIMIT :limit
    """
    with eng.connect() as conn:
        rows = list(conn.execute(text(sql), params).mappings())
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "score": float(row["score"] or 0.0),
                "metadata": {
                    "practice_area": row["practice_area"],
                    "jurisdictions": list(row["jurisdictions"] or []),
                    "doc_type": row["doc_type"],
                },
            }
        )
    return out


# Thin wrappers used by callers that expect a table-like object with count_rows().
class _PgTable:
    def count_rows(self) -> int:
        return count_rows()


def open_table() -> _PgTable:
    ensure_kb_docs()
    return _PgTable()


if __name__ == "__main__":
    ensure_kb_docs()
    print(f"Postgres kb_docs ready; rows={count_rows()}")
