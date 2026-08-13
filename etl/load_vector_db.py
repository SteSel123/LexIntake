"""Load embedded chunks into a local vector store.

Pipeline properties:
- Re-runnable: safe to execute repeatedly
- Idempotent: same KB inputs converge to the same store state
- Incremental: only re-embed / rewrite chunks whose content_hash changed
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from chunk import chunk_all
from clean import clean_all
from deduplicate import deduplicate_all
from embeddings import embed_chunks
from extract import extract_all
from metadata import attach_metadata_all

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "vector_store.json"


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


def run_pipeline(db_path: Path | None = None, full_refresh: bool = False) -> LocalVectorDB:
    """
    Extract → clean → deduplicate → chunk → metadata → embed → load.

    Incremental by default: unchanged content_hash values reuse embeddings.
    Set full_refresh=True to re-embed everything.
    """
    documents = extract_all()
    cleaned = clean_all(documents)
    unique = deduplicate_all(cleaned)
    chunks = chunk_all(unique)
    enriched = attach_metadata_all(chunks)

    db = LocalVectorDB(path=db_path)
    db.load()
    existing = {} if full_refresh else db.by_id()

    embedded, embed_stats = embed_chunks(enriched, existing_by_id=existing)
    upserted = db.upsert(embedded)
    pruned = db.prune_missing({r["chunk_id"] for r in embedded if r.get("chunk_id")})
    db.save()

    print(
        "Pipeline complete: "
        f"extracted={len(documents)} cleaned={len(cleaned)} unique={len(unique)} "
        f"chunks={len(chunks)} embedded={embed_stats['embedded']} "
        f"reused={embed_stats['reused']} upserted_changed={upserted} "
        f"pruned={pruned} store={db.path}"
    )
    return db


if __name__ == "__main__":
    run_pipeline()
