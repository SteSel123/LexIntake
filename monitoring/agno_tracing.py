"""Agno native tracing / monitoring for LexIntake."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MON_DIR = Path(__file__).resolve().parent
TRACES_DB = MON_DIR / "traces.db"

logger = logging.getLogger("lexintake.monitoring.agno")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_ENABLED = False
_TRACE_DB: Any | None = None


def enable_agno_monitoring(*, force: bool = False) -> bool:
    """
    Enable Agno OpenTelemetry tracing once per process.

    Stores spans in monitoring/traces.db (local Agno Monitoring).
    Disable with LEXINTAKE_AGNO_TRACING=0 (used by offline CI).
    """
    global _ENABLED, _TRACE_DB
    if _ENABLED and not force:
        return True

    flag = os.getenv("LEXINTAKE_AGNO_TRACING", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        logger.info("Agno tracing disabled via LEXINTAKE_AGNO_TRACING")
        return False

    # Skip in pure offline/hash CI unless explicitly forced.
    provider = (os.getenv("LEXINTAKE_LLM_PROVIDER") or "").lower()
    if provider in {"local", "deterministic", "hash", "none"} and not force:
        if os.getenv("LEXINTAKE_FORCE_AGNO_TRACING", "").lower() not in {"1", "true", "yes"}:
            logger.info("Agno tracing skipped for deterministic provider=%s", provider)
            return False

    try:
        from agno.db.sqlite import SqliteDb
        from agno.tracing import setup_tracing
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agno tracing imports unavailable: %s", exc)
        return False

    try:
        TRACES_DB.parent.mkdir(parents=True, exist_ok=True)
        db = SqliteDb(db_file=str(TRACES_DB), id="lexintake_traces")
        setup_tracing(db=db, batch_processing=False)
        _TRACE_DB = db
        _ENABLED = True
        logger.info("Agno monitoring enabled → %s", TRACES_DB)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to enable Agno tracing: %s", exc)
        return False


def tracing_enabled() -> bool:
    return _ENABLED


def get_trace_db() -> Any | None:
    return _TRACE_DB


def recent_traces(limit: int = 20) -> list[dict[str, Any]]:
    """Best-effort query of recent Agno traces for the dashboard."""
    db = _TRACE_DB
    if db is None:
        try:
            from agno.db.sqlite import SqliteDb

            if not TRACES_DB.exists():
                return []
            db = SqliteDb(db_file=str(TRACES_DB), id="lexintake_traces")
        except Exception:  # noqa: BLE001
            return []

    try:
        traces, _count = db.get_traces(limit=limit)
        out: list[dict[str, Any]] = []
        for t in traces or []:
            if hasattr(t, "to_dict"):
                out.append(t.to_dict())
            elif isinstance(t, dict):
                out.append(t)
            else:
                out.append(
                    {
                        "trace_id": getattr(t, "trace_id", None),
                        "status": getattr(t, "status", None),
                        "duration": getattr(t, "duration", None),
                        "name": getattr(t, "name", None),
                    }
                )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.debug("recent_traces failed: %s", exc)
        return []


if __name__ == "__main__":
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    ok = enable_agno_monitoring(force=True)
    print(f"enabled={ok} db={TRACES_DB} exists={TRACES_DB.exists()}")
