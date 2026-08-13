"""Structured JSON logger for LexIntake observability (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

# Optional sink for in-process metrics bridging (set by metrics module).
_metrics_hook: Callable[[str, dict[str, Any]], None] | None = None
_lock = threading.Lock()
_clock: Callable[[], datetime] | None = None

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "logs" / "lexintake.jsonl"


def set_clock(clock: Callable[[], datetime] | None) -> None:
    """Override clock for deterministic tests. Pass None to restore UTC now."""
    global _clock
    _clock = clock


def set_metrics_hook(hook: Callable[[str, dict[str, Any]], None] | None) -> None:
    """Register a callback invoked for each structured event (metrics bridge)."""
    global _metrics_hook
    _metrics_hook = hook


def _utcnow() -> datetime:
    if _clock is not None:
        return _clock()
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
    """
    Redact sensitive fields. Never log client PII, attorney private info, or raw KB text.
    """
    blocked = {
        "name",
        "email",
        "phone",
        "client_name",
        "opposing_party",
        "narrative",
        "facts",
        "text",
        "raw",
        "excerpt",
        "explanation",  # may contain free text; keep only short codes elsewhere
        "address",
        "ssn",
        "dob",
    }
    clean: dict[str, Any] = {}
    for key, value in data.items():
        lk = str(key).lower()
        if lk in blocked or lk.endswith("_name") and lk not in {"tool_name", "step_name", "event_type"}:
            continue
        if lk in {"query", "retrieval_query"}:
            text = str(value or "")
            clean["query_len"] = len(text)
            clean["query_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            continue
        if isinstance(value, dict):
            clean[key] = _sanitize(value)
        elif isinstance(value, list):
            clean[key] = [
                _sanitize(v) if isinstance(v, dict) else v
                for v in value
                if not isinstance(v, str) or len(v) < 80
            ]
        else:
            clean[key] = value
    return clean


class StructuredLogger:
    """Thread-safe JSONL logger with session scoping."""

    def __init__(
        self,
        session_id: str | None = None,
        log_path: Path | str | None = None,
        agent_id: str = "intake",
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.agent_id = agent_id
        self.log_path = Path(log_path or DEFAULT_LOG_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def bind(self, session_id: str | None = None, agent_id: str | None = None) -> StructuredLogger:
        """Return a child logger for another agent/session (multi-agent safe)."""
        return StructuredLogger(
            session_id=session_id or self.session_id,
            log_path=self.log_path,
            agent_id=agent_id or self.agent_id,
        )

    def log_event(self, event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "ts": _ts(),
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "event_type": event_type,
            "data": _sanitize(data or {}),
        }
        line = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        with _lock:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            if _metrics_hook is not None:
                try:
                    _metrics_hook(event_type, payload)
                except Exception:
                    pass
        return payload

    def log_latency(self, step_name: str, ms: float) -> dict[str, Any]:
        return self.log_event("latency", {"step_name": step_name, "ms": round(float(ms), 3)})

    def log_tool_call(self, tool_name: str, success: bool, duration_ms: float) -> dict[str, Any]:
        return self.log_event(
            "tool_call",
            {
                "tool_name": tool_name,
                "success": bool(success),
                "duration_ms": round(float(duration_ms), 3),
            },
        )

    def log_retrieval(self, query: str, hits: int, total_chunks: int) -> dict[str, Any]:
        hit_rate = (float(hits) / float(total_chunks)) if total_chunks else 0.0
        return self.log_event(
            "retrieval",
            {
                "query": query,  # sanitized to hash/len
                "hits": int(hits),
                "total_chunks": int(total_chunks),
                "hit_rate": round(hit_rate, 6),
            },
        )

    def log_lead_score(self, score: int) -> dict[str, Any]:
        return self.log_event("lead_score", {"score": int(score)})

    def log_escalation(self, reason: str) -> dict[str, Any]:
        # Keep reason as a short code/category only
        safe_reason = str(reason or "unknown")[:120]
        return self.log_event("escalation", {"reason": safe_reason})

    def log_case_value(self, estimate: float) -> dict[str, Any]:
        return self.log_event("case_value", {"estimate": float(estimate)})

    def log_tokens(self, tokens: int, cost: float | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"tokens": int(tokens)}
        if cost is not None:
            data["cost"] = float(cost)
        return self.log_event("tokens", data)


# Module-level default logger (session created lazily per call site via get_logger).
_default_logger: StructuredLogger | None = None
_default_lock = threading.Lock()


def get_logger(session_id: str | None = None, agent_id: str = "intake") -> StructuredLogger:
    """Get a process-wide logger, optionally rebound to a session."""
    global _default_logger
    with _default_lock:
        if _default_logger is None:
            _default_logger = StructuredLogger(session_id=session_id, agent_id=agent_id)
            return _default_logger
        if session_id and session_id != _default_logger.session_id:
            return _default_logger.bind(session_id=session_id, agent_id=agent_id)
        return _default_logger


# Convenience aliases matching the required API surface.
def log_event(event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_logger().log_event(event_type, data)


def log_latency(step_name: str, ms: float) -> dict[str, Any]:
    return get_logger().log_latency(step_name, ms)


def log_tool_call(tool_name: str, success: bool, duration_ms: float) -> dict[str, Any]:
    return get_logger().log_tool_call(tool_name, success, duration_ms)


def log_retrieval(query: str, hits: int, total_chunks: int) -> dict[str, Any]:
    return get_logger().log_retrieval(query, hits, total_chunks)


def log_lead_score(score: int) -> dict[str, Any]:
    return get_logger().log_lead_score(score)


def log_escalation(reason: str) -> dict[str, Any]:
    return get_logger().log_escalation(reason)


def log_case_value(estimate: float) -> dict[str, Any]:
    return get_logger().log_case_value(estimate)


@contextmanager
def tool_span(tool_name: str) -> Iterator[None]:
    """Context manager to log tool latency/success without capturing payloads."""
    start = time.perf_counter()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        log_tool_call(tool_name, success, (time.perf_counter() - start) * 1000.0)


@contextmanager
def step_span(step_name: str) -> Iterator[None]:
    """Context manager to log phase latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        log_latency(step_name, (time.perf_counter() - start) * 1000.0)
