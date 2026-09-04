"""Extract stage: read raw knowledge-base sources into document records."""

from __future__ import annotations

from typing import Any

__all__ = ["extract_all"]


def __getattr__(name: str) -> Any:
    if name == "extract_all":
        from etl.extract.documents import extract_all

        return extract_all
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
