"""Attach retrieval metadata to chunks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


PIPELINE_VERSION = "1.0.0"


def build_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """Derive structured metadata for a chunk."""
    text = chunk.get("text") or ""
    practice_area = chunk.get("practice_area")
    source = chunk.get("source")
    doc_type = chunk.get("doc_type")

    tags = [t for t in [doc_type, practice_area, source] if t]
    jurisdictions: list[str] = []

    raw = chunk.get("raw")
    if isinstance(raw, dict):
        if isinstance(raw.get("jurisdictions"), list):
            jurisdictions = [str(j) for j in raw["jurisdictions"]]
        elif isinstance(raw.get("jurisdiction"), str):
            jurisdictions = [raw["jurisdiction"]]
        # SOL tables are keyed by state code
        elif doc_type == "sol_rules":
            jurisdictions = [str(k) for k in raw.keys()]

    return {
        "chunk_id": chunk.get("chunk_id"),
        "content_hash": chunk.get("content_hash"),
        "source": source,
        "doc_type": doc_type,
        "practice_area": practice_area,
        "item_index": chunk.get("item_index"),
        "chunk_index": chunk.get("chunk_index"),
        "jurisdictions": jurisdictions,
        "tags": tags,
        "char_count": len(text),
        "word_count": len(text.split()),
        "pipeline_version": PIPELINE_VERSION,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


def attach_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """Return chunk with a metadata object attached."""
    enriched = dict(chunk)
    enriched["metadata"] = build_metadata(chunk)
    return enriched


def attach_metadata_all(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach metadata to a batch of chunks."""
    return [attach_metadata(chunk) for chunk in chunks]


if __name__ == "__main__":
    from chunk import chunk_all
    from clean import clean_all
    from deduplicate import deduplicate_all
    from extract import extract_all

    enriched = attach_metadata_all(chunk_all(deduplicate_all(clean_all(extract_all()))))
    print(f"Enriched {len(enriched)} chunks")
    print(enriched[0]["metadata"] if enriched else "No chunks")
