"""Compose the ETL stages: extract → transform → (embed + load)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.extract import extract_all
from etl.transform import chunk_all
from etl.transform import clean_all
from etl.transform import deduplicate_all
from etl.transform import embed_chunks
from etl.transform import attach_metadata_all


def run_pipeline(
    db_path: Path | None = None,
    full_refresh: bool = False,
    *,
    write_json: bool = False,
    recreate_on_dim_mismatch: bool = False,
) -> dict[str, Any]:
    """Extract → transform → embed → load."""
    from etl.load.vector_db import existing_by_id

    documents = extract()
    stages = transform(documents)
    cleaned = stages["cleaned"]
    unique = stages["unique"]
    chunks = stages["chunks"]
    enriched = stages["enriched"]

    existing = {} if full_refresh else existing_by_id(db_path)
    embedded, embed_stats = embed(enriched, existing_by_id=existing)
    load_stats = load(
        embedded,
        db_path=db_path,
        write_json=write_json,
        recreate_on_dim_mismatch=recreate_on_dim_mismatch,
    )
    lance_stats = load_stats["lance_stats"]
    json_changed = load_stats["json_changed"]

    print(
        "Pipeline complete: "
        f"extracted={len(documents)} cleaned={len(cleaned)} unique={len(unique)} "
        f"chunks={len(chunks)} embedded={embed_stats['embedded']} "
        f"reused={embed_stats['reused']} lance_inserted={lance_stats['inserted']} "
        f"lance_updated={lance_stats['updated']} lance_total={lance_stats['total']} "
        f"json_changed={json_changed}"
    )
    return {"embed_stats": embed_stats, "lance_stats": lance_stats, "json_changed": json_changed}


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
    db_path: Path | None = None,
    write_json: bool = False,
    dimensions: int | None = None,
    recreate_on_dim_mismatch: bool = False,
) -> dict[str, Any]:
    """Persist embedded chunks into vector storage."""
    from etl.load.vector_db import load as persist

    return persist(
        records,
        db_path=db_path,
        write_json=write_json,
        dimensions=dimensions,
        recreate_on_dim_mismatch=recreate_on_dim_mismatch,
    )


if __name__ == "__main__":
    run_pipeline()
