"""Load stage: lazy export of ``load`` and ``existing_by_id`` for the pipeline."""

from __future__ import annotations

from typing import Any

__all__ = ["existing_by_id", "load"]


def __getattr__(name: str) -> Any:
    """Defer import of ``vector_db`` until load helpers are accessed."""
    if name in {"existing_by_id", "load"}:
        from etl.load import vector_db as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
