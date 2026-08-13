"""JSON-lines logger for LexIntake evaluation runs."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "logs" / "evaluation.jsonl"
_lock = threading.Lock()


def _ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize(value: Any) -> Any:
    """Avoid logging raw sensitive fields / long free text."""
    if isinstance(value, dict):
        blocked = {
            "name",
            "email",
            "phone",
            "opposing_party",
            "narrative",
            "message",
            "explanation",
            "text",
            "excerpt",
            "facts",
        }
        out: dict[str, Any] = {}
        for k, v in value.items():
            lk = str(k).lower()
            if lk in blocked:
                continue
            if lk in {"description", "input_text", "query"}:
                text = str(v or "")
                out[f"{k}_len"] = len(text)
                out[f"{k}_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                continue
            out[k] = _sanitize(v)
        return out
    if isinstance(value, list):
        return [_sanitize(v) for v in value[:50]]
    return value


class EvalLogger:
    def __init__(self, log_path: Path | str | None = None) -> None:
        self.log_path = Path(log_path or DEFAULT_LOG_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "ts": _ts(),
            "event_type": event_type,
            "data": _sanitize(payload),
        }
        line = json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        with _lock:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return record

    def log_result(self, lead_id: str, input_data: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        return self._write(
            "result",
            {"lead_id": lead_id, "input": input_data, "output": output},
        )

    def log_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        return self._write("metrics", metrics)

    def log_guardrail_violation(self, lead_id: str, issue: str) -> dict[str, Any]:
        return self._write(
            "guardrail_violation",
            {"lead_id": lead_id, "issue": str(issue)[:200]},
        )

    def log_abstention(self, lead_id: str) -> dict[str, Any]:
        return self._write("abstention", {"lead_id": lead_id})

    def log_retrieval_quality(self, lead_id: str, hits: int, misses: int) -> dict[str, Any]:
        total = hits + misses
        return self._write(
            "retrieval_quality",
            {
                "lead_id": lead_id,
                "hits": int(hits),
                "misses": int(misses),
                "hit_rate": (hits / total) if total else 0.0,
            },
        )

    def log_grounding(self, lead_id: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
        safe_cites = [
            {
                "chunk_id": c.get("chunk_id"),
                "practice_area": c.get("practice_area"),
                "doc_type": c.get("doc_type"),
            }
            for c in citations
            if isinstance(c, dict)
        ]
        return self._write("grounding", {"lead_id": lead_id, "citations": safe_cites})

    def log_provider_result(self, provider: str, lead_id: str, output: dict[str, Any]) -> dict[str, Any]:
        return self._write(
            "provider_result",
            {"provider": provider, "lead_id": lead_id, "output": output},
        )


# Module-level helpers
_default = EvalLogger()


def log_result(lead_id: str, input_data: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    return _default.log_result(lead_id, input_data, output)


def log_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return _default.log_metrics(metrics)


def log_guardrail_violation(lead_id: str, issue: str) -> dict[str, Any]:
    return _default.log_guardrail_violation(lead_id, issue)


def log_abstention(lead_id: str) -> dict[str, Any]:
    return _default.log_abstention(lead_id)


def log_retrieval_quality(lead_id: str, hits: int, misses: int) -> dict[str, Any]:
    return _default.log_retrieval_quality(lead_id, hits, misses)


def log_grounding(lead_id: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
    return _default.log_grounding(lead_id, citations)


def log_provider_result(provider: str, lead_id: str, output: dict[str, Any]) -> dict[str, Any]:
    return _default.log_provider_result(provider, lead_id, output)
