"""Generate embeddings for chunked KB documents (OpenAI or hash fallback)."""

from __future__ import annotations

import hashlib
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from config import (
        EMBED_DIMS,
        EMBED_MODEL,
        EMBED_PROVIDER,
        OPENAI_API_KEY,
        require_openai_api_key,
    )
except ImportError:  # pragma: no cover
    EMBED_PROVIDER = os.getenv("LEXINTAKE_EMBEDDING_PROVIDER", "hash")
    EMBED_MODEL = os.getenv("LEXINTAKE_EMBEDDING_MODEL", "hash-v1")
    EMBED_DIMS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "256"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    def require_openai_api_key() -> str:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is missing")
        return OPENAI_API_KEY


TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)
DEFAULT_MODEL = EMBED_MODEL
DEFAULT_DIMENSIONS = EMBED_DIMS


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbedder:
    """Deterministic offline embedder (dev fallback)."""

    def __init__(self, dimensions: int = 256, model_name: str = "hash-v1") -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be >= 8")
        self.dimensions = dimensions
        self.model_name = model_name

    def _tokenize(self, token: str) -> list[float]:
        vector = [0.0] * self.dimensions
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(self.dimensions):
            byte = digest[i % len(digest)]
            vector[i] = (byte / 255.0) * 2.0 - 1.0
        return vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            tokens = TOKEN_RE.findall(text.lower())
            if not tokens:
                vectors.append([0.0] * self.dimensions)
                continue
            acc = [0.0] * self.dimensions
            for token in tokens:
                token_vec = self._tokenize(token)
                for i, value in enumerate(token_vec):
                    acc[i] += value
            norm = math.sqrt(sum(v * v for v in acc)) or 1.0
            vectors.append([v / norm for v in acc])
        return vectors


class OpenAIEmbedderAdapter:
    """Adapter around Agno OpenAIEmbedder exposing LexIntake .embed(texts)."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        self.model_name = model_name or EMBED_MODEL
        key = api_key or require_openai_api_key()
        dims = dimensions or EMBED_DIMS
        self._inner = OpenAIEmbedder(
            id=self.model_name,
            api_key=key,
            dimensions=dims,
            enable_batch=True,
            batch_size=64,
        )
        self.dimensions = int(self._inner.dimensions or dims)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for text in texts:
            vec = self._inner.get_embedding(text or " ")
            if not vec:
                vectors.append([0.0] * self.dimensions)
            else:
                vectors.append([float(x) for x in vec])
        return vectors


def get_embedder(provider: str | None = None) -> Embedder:
    """Factory for the active embedder implementation."""
    active = (provider or EMBED_PROVIDER or "openai").lower()
    if active in {"openai", "openai_embedder"}:
        return OpenAIEmbedderAdapter()
    if active == "hash":
        return HashEmbedder(dimensions=min(EMBED_DIMS, 256), model_name="hash-v1")
    raise ValueError(
        f"Unsupported LEXINTAKE_EMBEDDING_PROVIDER={active!r}. Supported: openai, hash."
    )


def _needs_embedding(chunk: dict[str, Any], existing: dict[str, Any] | None, model: Embedder) -> bool:
    if not existing:
        return True
    if existing.get("embedding_model") != model.model_name:
        return True
    if existing.get("embedding_dimensions") != model.dimensions:
        return True
    existing_hash = (existing.get("metadata") or {}).get("content_hash") or existing.get("content_hash")
    return existing_hash != chunk.get("content_hash")


def embed_chunks(
    chunks: list[dict[str, Any]],
    embedder: Embedder | None = None,
    existing_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Attach embedding vectors to chunks (incremental when possible)."""
    model = embedder or get_embedder()
    existing_by_id = existing_by_id or {}

    to_embed: list[dict[str, Any]] = []
    reuse: list[dict[str, Any]] = []

    for chunk in chunks:
        prior = existing_by_id.get(chunk.get("chunk_id"))
        if _needs_embedding(chunk, prior, model):
            to_embed.append(chunk)
        else:
            reused = dict(chunk)
            reused["embedding"] = prior.get("embedding")
            reused["embedding_model"] = prior.get("embedding_model")
            reused["embedding_dimensions"] = prior.get("embedding_dimensions")
            reuse.append(reused)

    vectors = model.embed([c.get("text", "") for c in to_embed]) if to_embed else []
    embedded: list[dict[str, Any]] = []
    for chunk, vector in zip(to_embed, vectors, strict=True):
        record = dict(chunk)
        record["embedding"] = vector
        record["embedding_model"] = model.model_name
        record["embedding_dimensions"] = model.dimensions
        embedded.append(record)

    by_id = {r["chunk_id"]: r for r in reuse + embedded}
    ordered = [by_id[c["chunk_id"]] for c in chunks if c.get("chunk_id") in by_id]
    stats = {"embedded": len(embedded), "reused": len(reuse), "total": len(ordered)}
    return ordered, stats


if __name__ == "__main__":
    from etl.extract.documents import extract_all
    from etl.transform.chunk import chunk_all
    from etl.transform.clean import clean_all
    from etl.transform.deduplicate import deduplicate_all
    from etl.transform.metadata import attach_metadata_all

    records, stats = embed_chunks(
        attach_metadata_all(chunk_all(deduplicate_all(clean_all(extract_all()))))
    )
    print(f"Embedded stats={stats} model={records[0]['embedding_model']}")
    print(f"dims={records[0]['embedding_dimensions']} first5={records[0]['embedding'][:5]}")
