"""Transform stage: clean, deduplicate, chunk, enrich, and embed documents."""

from __future__ import annotations

from typing import Any

__all__ = [
    "attach_metadata_all",
    "chunk_all",
    "chunk_document",
    "clean_all",
    "clean_document",
    "content_hash",
    "deduplicate_all",
    "embed_chunks",
    "get_embedder",
    "normalize_text",
]


def __getattr__(name: str) -> Any:
    if name in {"clean_all", "clean_document", "normalize_text"}:
        from etl.transform import clean as module

        return getattr(module, name)
    if name in {"content_hash", "deduplicate_all"}:
        from etl.transform import deduplicate as module

        return getattr(module, name)
    if name in {"chunk_all", "chunk_document"}:
        from etl.transform import chunk as module

        return getattr(module, name)
    if name == "attach_metadata_all":
        from etl.transform.metadata import attach_metadata_all

        return attach_metadata_all
    if name in {"embed_chunks", "get_embedder"}:
        from etl.transform import embeddings as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
