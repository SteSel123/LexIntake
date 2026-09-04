"""Load stage: persist transformed chunks into vector storage."""

from __future__ import annotations

from typing import Any

__all__ = ["LocalVectorDB", "existing_by_id", "load"]


def __getattr__(name: str) -> Any:
    if name in {"LocalVectorDB", "existing_by_id", "load"}:
        from etl.load import vector_db as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
