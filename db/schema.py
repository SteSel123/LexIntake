"""Shared KB collection constants (PostgreSQL kb_docs)."""

from __future__ import annotations

import os

COLLECTION_NAME = "kb_docs"
DEFAULT_EMBEDDING_DIMS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "1536"))
