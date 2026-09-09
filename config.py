"""LexIntake runtime configuration (loaded from environment / .env)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

LLM_PROVIDER = os.getenv("LEXINTAKE_LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LEXINTAKE_LLM_MODEL", "gpt-4.1")

EMBED_PROVIDER = os.getenv("LEXINTAKE_EMBEDDING_PROVIDER", "openai")
EMBED_MODEL = os.getenv("LEXINTAKE_EMBEDDING_MODEL", "text-embedding-3-small")
EMBED_DIMS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "1536"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Required: PostgreSQL with pgvector (entities + heterogeneous KB chunks).
DATABASE_URL = (os.getenv("DATABASE_URL") or os.getenv("LEXINTAKE_DATABASE_URL") or "").strip()

# Keep env vars in sync for libraries that read them directly.
if OPENAI_API_KEY:
    os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY)


def require_openai_api_key() -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Copy .env.example to .env and set your key."
        )
    return OPENAI_API_KEY


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing. Start Postgres (docker compose up -d) and set "
            "DATABASE_URL=postgresql://lexintake:lexintake@localhost:5432/lexintake"
        )
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if not url.startswith(("postgresql://", "postgresql+")):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL URL "
            "(postgresql://user:pass@host:5432/dbname)."
        )
    # Prefer psycopg v3 (package ``psycopg``) over legacy psycopg2.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url
