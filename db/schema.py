"""Shared KB collection constants (PostgreSQL kb_docs).

Single source of truth for the vector table name and default embedding width
so ETL, pgvector_store, and migrations stay aligned.
"""

from __future__ import annotations

import os

COLLECTION_NAME = "kb_docs"
DEFAULT_EMBEDDING_DIMS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "1536"))
