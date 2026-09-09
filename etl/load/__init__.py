"""Load stage: persist transformed chunks into PostgreSQL kb_docs."""

from __future__ import annotations

from typing import Any

__all__ = ["existing_by_id", "load"]


def __getattr__(name: str) -> Any:
    if name in {"existing_by_id", "load"}:
        from etl.load import vector_db as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
