"""Split cleaned documents into retrieval-friendly chunks."""

from __future__ import annotations

import hashlib
from typing import Any


DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


def _chunk_id(content_hash: str | None, source: str, practice_area: str | None, index: int, text: str) -> str:
    """Stable chunk identity: same content → same id (idempotent re-runs)."""
    basis = content_hash or f"{source}|{practice_area or ''}|{text}"
    return hashlib.sha256(f"{basis}|{index}".encode("utf-8")).hexdigest()[:16]


def split_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character windows, preferring paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(paragraph) <= chunk_size:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + chunk_size, len(paragraph))
            chunks.append(paragraph[start:end].strip())
            if end >= len(paragraph):
                current = ""
                break
            start = max(0, end - overlap)
        current = ""

    if current:
        chunks.append(current)

    return [c for c in chunks if c]


def chunk_document(
    doc: dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Chunk one document into multiple records."""
    parts = split_text(doc.get("text", ""), chunk_size=chunk_size, overlap=overlap)
    chunks: list[dict[str, Any]] = []

    for index, part in enumerate(parts):
        chunk = {
            "chunk_id": _chunk_id(
                doc.get("content_hash"),
                doc.get("source", ""),
                doc.get("practice_area"),
                index,
                part,
            ),
            "source": doc.get("source"),
            "doc_type": doc.get("doc_type"),
            "practice_area": doc.get("practice_area"),
            "item_index": doc.get("item_index"),
            "chunk_index": index,
            "content_hash": doc.get("content_hash"),
            "text": part,
            "raw": doc.get("raw"),
        }
        chunks.append(chunk)

    return chunks


def chunk_all(
    documents: list[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Chunk a batch of documents."""
    chunks: list[dict[str, Any]] = []
    for doc in documents:
        chunks.extend(chunk_document(doc, chunk_size=chunk_size, overlap=overlap))
    return chunks


if __name__ == "__main__":
    from etl.extract.documents import extract_all
    from etl.transform.clean import clean_all
    from etl.transform.deduplicate import deduplicate_all

    chunks = chunk_all(deduplicate_all(clean_all(extract_all())))
    print(f"Created {len(chunks)} chunks")
    print(chunks[0] if chunks else "No chunks")
