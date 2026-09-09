"""Compose the ETL stages: extract → transform → (embed + load)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from etl.extract import extract_all
from etl.transform import attach_metadata_all, chunk_all, clean_all, deduplicate_all, embed_chunks


def run_pipeline(
    *,
    full_refresh: bool = False,
    recreate_on_dim_mismatch: bool = False,
) -> dict[str, Any]:
    """Extract → transform → embed → load into Postgres kb_docs."""
    from etl.load.vector_db import existing_by_id

    documents = extract()
    stages = transform(documents)
    cleaned = stages["cleaned"]
    unique = stages["unique"]
    chunks = stages["chunks"]
    enriched = stages["enriched"]

    existing = {} if full_refresh else existing_by_id()
    embedded, embed_stats = embed(enriched, existing_by_id=existing)
    load_stats = load(
        embedded,
        recreate_on_dim_mismatch=recreate_on_dim_mismatch,
    )
    pg_stats = load_stats.get("pg_stats") or {}

    backend = load_stats.get("backend", "postgres")
    print(
        "Pipeline complete: "
        f"backend={backend} "
        f"extracted={len(documents)} cleaned={len(cleaned)} unique={len(unique)} "
        f"chunks={len(chunks)} embedded={embed_stats['embedded']} "
        f"reused={embed_stats['reused']} inserted={pg_stats.get('inserted', 0)} "
        f"updated={pg_stats.get('updated', 0)} total={pg_stats.get('total', 0)}"
    )
    return {
        "backend": backend,
        "embed_stats": embed_stats,
        "pg_stats": pg_stats,
    }


def extract(*, kb_dir: Path | None = None) -> list[dict[str, Any]]:
    """Extract raw documents from the knowledge base."""
    return extract_all(kb_dir)


def transform(documents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Clean, deduplicate, chunk, and attach metadata."""
    cleaned = clean_all(documents)
    unique = deduplicate_all(cleaned)
    chunks = chunk_all(unique)
    enriched = attach_metadata_all(chunks)
    return {
        "cleaned": cleaned,
        "unique": unique,
        "chunks": chunks,
        "enriched": enriched,
    }


def embed(
    chunks: list[dict[str, Any]],
    *,
    embedder: Any | None = None,
    existing_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Generate or reuse embeddings for transformed chunks."""
    return embed_chunks(chunks, embedder=embedder, existing_by_id=existing_by_id)


def load(
    records: list[dict[str, Any]],
    *,
    dimensions: int | None = None,
    recreate_on_dim_mismatch: bool = False,
) -> dict[str, Any]:
    """Persist embedded chunks into Postgres vector storage."""
    from etl.load.vector_db import load as persist

    return persist(
        records,
        dimensions=dimensions,
        recreate_on_dim_mismatch=recreate_on_dim_mismatch,
    )


if __name__ == "__main__":
    run_pipeline()
