"""Load ETL-generated chunks into LanceDB kb_docs."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python db/load_kb_docs.py` and importing etl modules.
ROOT = Path(__file__).resolve().parent.parent
ETL_DIR = ROOT / "etl"
DB_DIR = Path(__file__).resolve().parent
for path in (str(ROOT), str(ETL_DIR), str(DB_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from chunk import chunk_all  # noqa: E402
from clean import clean_all  # noqa: E402
from deduplicate import deduplicate_all  # noqa: E402
from embeddings import DEFAULT_DIMENSIONS, embed_chunks  # noqa: E402
from extract import extract_all  # noqa: E402
from lancedb_store import connect, ensure_kb_docs, upsert_kb_docs  # noqa: E402
from metadata import attach_metadata_all  # noqa: E402


def run_load(*, full_refresh: bool = False) -> dict:
    """
    Extract → clean → deduplicate → chunk → metadata → embed → LanceDB upsert.

    Incremental upsert retains existing kb_docs rows not present in this batch.
    """
    documents = extract_all()
    cleaned = clean_all(documents)
    unique = deduplicate_all(cleaned)
    chunks = chunk_all(unique)
    enriched = attach_metadata_all(chunks)

    # Always re-embed for LanceDB load path unless we later persist content_hash.
    # full_refresh currently only documents intent; embeddings are deterministic.
    _ = full_refresh
    embedded, embed_stats = embed_chunks(enriched)

    db = connect()
    table = ensure_kb_docs(db, dimensions=DEFAULT_DIMENSIONS)
    stats = upsert_kb_docs(
        embedded,
        db=db,
        table=table,
        dimensions=DEFAULT_DIMENSIONS,
    )

    print(
        "kb_docs load complete: "
        f"extracted={len(documents)} cleaned={len(cleaned)} unique={len(unique)} "
        f"chunks={len(chunks)} embedded={embed_stats['embedded']} "
        f"reused={embed_stats['reused']} upsert_received={stats['received']} "
        f"inserted={stats['inserted']} updated={stats['updated']} "
        f"deleted={stats['deleted']} total={stats['total']}"
    )
    return stats


if __name__ == "__main__":
    run_load()
