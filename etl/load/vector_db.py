"""Load embedded chunks into LanceDB (kb_docs) and optional JSON store.

Load properties:
- Re-runnable: safe to execute repeatedly
- Idempotent: upsert by chunk_id (no duplicates)
- Incremental: new/changed chunks upserted; existing rows retained
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

from etl.transform.embeddings import DEFAULT_DIMENSIONS

ROOT = Path(__file__).resolve().parents[2]
DB_PKG = ROOT / "db"
if str(DB_PKG) not in sys.path:
    sys.path.insert(0, str(DB_PKG))

from lancedb_store import connect, ensure_kb_docs, upsert_kb_docs  # noqa: E402

DEFAULT_DB_PATH = ROOT / "db" / "vector_store.json"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class LocalVectorDB:
    """Simple JSON-backed vector store for LexIntake development."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_DB_PATH
        self.records: list[dict[str, Any]] = []

    def load(self) -> None:
        if not self.path.exists():
            self.records = []
            return
        with self.path.open(encoding="utf-8") as f:
            payload = json.load(f)
        self.records = payload.get("records", [])

    def by_id(self) -> dict[str, dict[str, Any]]:
        return {r["chunk_id"]: r for r in self.records if r.get("chunk_id")}

    def upsert(self, records: list[dict[str, Any]]) -> int:
        """Idempotent upsert by chunk_id; preserve indexed_at when content is unchanged."""
        by_id = self.by_id()
        changed = 0
        for record in records:
            chunk_id = record.get("chunk_id")
            if not chunk_id:
                continue

            content_hash = record.get("content_hash") or (record.get("metadata") or {}).get(
                "content_hash"
            )
            metadata = dict(record.get("metadata") or {})
            prior = by_id.get(chunk_id)

            if prior and prior.get("content_hash") == content_hash:
                prior_meta = prior.get("metadata") or {}
                if prior_meta.get("indexed_at"):
                    metadata["indexed_at"] = prior_meta["indexed_at"]

            next_record = {
                "chunk_id": chunk_id,
                "content_hash": content_hash,
                "text": record.get("text"),
                "embedding": record.get("embedding"),
                "embedding_model": record.get("embedding_model"),
                "embedding_dimensions": record.get("embedding_dimensions"),
                "metadata": metadata,
            }
            if prior != next_record:
                changed += 1
            by_id[chunk_id] = next_record
        self.records = list(by_id.values())
        return changed

    def prune_missing(self, active_chunk_ids: set[str]) -> int:
        """Remove records that are no longer produced by the pipeline (idempotent sync)."""
        before = len(self.records)
        self.records = [r for r in self.records if r.get("chunk_id") in active_chunk_ids]
        return before - len(self.records)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Stable ordering makes file diffs deterministic across re-runs
        ordered = sorted(self.records, key=lambda r: r.get("chunk_id") or "")
        payload = {
            "store": "lexintake-local-vector-db",
            "count": len(ordered),
            "records": ordered,
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        practice_area: str | None = None,
    ) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        for record in self.records:
            metadata = record.get("metadata") or {}
            if practice_area and metadata.get("practice_area") != practice_area:
                continue
            score = _cosine_similarity(query_embedding, record.get("embedding") or [])
            scored.append(
                {
                    "chunk_id": record.get("chunk_id"),
                    "score": score,
                    "text": record.get("text"),
                    "metadata": metadata,
                }
            )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]


def existing_by_id(db_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return previously persisted records keyed by chunk_id (for incremental embed)."""
    json_db = LocalVectorDB(path=db_path)
    json_db.load()
    return json_db.by_id()


def load(
    records: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
    write_json: bool = False,
    dimensions: int | None = None,
    recreate_on_dim_mismatch: bool = False,
) -> dict[str, Any]:
    """Persist embedded chunks to LanceDB; optionally refresh the JSON store."""
    dims = dimensions or DEFAULT_DIMENSIONS
    lance = connect()
    table = ensure_kb_docs(
        lance,
        dimensions=dims,
        recreate_on_dim_mismatch=recreate_on_dim_mismatch,
    )
    lance_stats = upsert_kb_docs(
        records,
        db=lance,
        table=table,
        dimensions=dims,
    )

    json_changed = 0
    if write_json:
        json_db = LocalVectorDB(path=db_path)
        json_db.load()
        json_changed = json_db.upsert(records)
        json_db.save()

    return {"lance_stats": lance_stats, "json_changed": json_changed}
