"""In-memory metrics collector for LexIntake monitoring."""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _day_key(ts: datetime | None = None) -> str:
    current = ts or datetime.now(timezone.utc)
    return current.strftime("%Y-%m-%d")


@dataclass
class Metrics:
    tokens_used: int = 0
    total_cost: float = 0.0
    latencies: dict[str, list[float]] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieval_stats: list[dict[str, Any]] = field(default_factory=list)
    lead_scores: list[int] = field(default_factory=list)
    escalations: list[dict[str, Any]] = field(default_factory=list)
    case_values: list[float] = field(default_factory=list)
    sol_failures: int = 0
    conflicts_detected: int = 0
    attorney_routes: list[str] = field(default_factory=list)
    sessions: list[str] = field(default_factory=list)
    daily_sessions: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    session_id: str | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def start_session(self, session_id: str) -> None:
        with self._lock:
            self.session_id = session_id
            if session_id not in self.sessions:
                self.sessions.append(session_id)
                self.daily_sessions[_day_key()] += 1

    def add_tokens(self, n: int) -> None:
        with self._lock:
            self.tokens_used += int(n)

    def add_cost(self, amount: float) -> None:
        with self._lock:
            self.total_cost += float(amount)

    def add_latency(self, step: str, ms: float) -> None:
        with self._lock:
            self.latencies.setdefault(step, []).append(float(ms))

    def add_tool_call(self, tool_name: str, duration_ms: float, success: bool) -> None:
        with self._lock:
            self.tool_calls.append(
                {
                    "tool_name": tool_name,
                    "duration_ms": float(duration_ms),
                    "success": bool(success),
                }
            )

    def add_retrieval(self, query: str, hits: int, total: int) -> None:
        with self._lock:
            hit_rate = (float(hits) / float(total)) if total else 0.0
            self.retrieval_stats.append(
                {
                    "query_len": len(query or ""),
                    "hits": int(hits),
                    "total": int(total),
                    "hit_rate": hit_rate,
                }
            )

    def add_lead_score(self, score: int) -> None:
        with self._lock:
            self.lead_scores.append(int(score))

    def add_escalation(self, reason: str) -> None:
        with self._lock:
            self.escalations.append({"reason": str(reason)[:120]})

    def add_case_value(self, estimate: float) -> None:
        with self._lock:
            self.case_values.append(float(estimate))

    def add_sol_failure(self) -> None:
        with self._lock:
            self.sol_failures += 1

    def add_conflict_detected(self) -> None:
        with self._lock:
            self.conflicts_detected += 1

    def add_attorney_route(self, attorney_key: str) -> None:
        """Store non-sensitive attorney routing key (slug/id only)."""
        with self._lock:
            key = str(attorney_key or "unassigned")[:80]
            self.attorney_routes.append(key)

    def retrieval_hit_rate(self) -> float:
        with self._lock:
            if not self.retrieval_stats:
                return 0.0
            return sum(r["hit_rate"] for r in self.retrieval_stats) / len(self.retrieval_stats)

    def total_latency_ms(self) -> float:
        with self._lock:
            return sum(sum(v) for v in self.latencies.values())

    def session_summary(self) -> dict[str, Any]:
        with self._lock:
            scores = list(self.lead_scores)
            values = list(self.case_values)
            tool_freq = Counter(t["tool_name"] for t in self.tool_calls)
            return {
                "session_id": self.session_id,
                "tokens_used": self.tokens_used,
                "cost": round(self.total_cost, 6),
                "total_latency_ms": round(self.total_latency_ms(), 3),
                "latencies": {k: list(v) for k, v in self.latencies.items()},
                "tool_calls": len(self.tool_calls),
                "tool_success_rate": (
                    sum(1 for t in self.tool_calls if t["success"]) / len(self.tool_calls)
                    if self.tool_calls
                    else 0.0
                ),
                "tool_usage": dict(tool_freq),
                "retrieval_hit_rate": round(self.retrieval_hit_rate(), 6),
                "lead_score_distribution": {
                    "count": len(scores),
                    "avg": round(sum(scores) / len(scores), 3) if scores else 0.0,
                    "min": min(scores) if scores else 0,
                    "max": max(scores) if scores else 0,
                    "values": scores,
                },
                "escalation_count": len(self.escalations),
                "case_value_distribution": {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 3) if values else 0.0,
                    "min": min(values) if values else 0.0,
                    "max": max(values) if values else 0.0,
                    "values": values,
                },
            }

    def daily_summary(self) -> dict[str, Any]:
        with self._lock:
            scores = list(self.lead_scores)
            values = list(self.case_values)
            routes = Counter(self.attorney_routes)
            return {
                "day": _day_key(),
                "total_sessions": len(self.sessions),
                "sessions_by_day": dict(self.daily_sessions),
                "average_lead_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
                "sol_failures": self.sol_failures,
                "conflicts_detected": self.conflicts_detected,
                "average_case_value": round(sum(values) / len(values), 3) if values else 0.0,
                "attorney_routing_distribution": dict(routes),
                "escalation_rate": (
                    len(self.escalations) / max(1, len(self.sessions))
                    if self.sessions
                    else (1.0 if self.escalations else 0.0)
                ),
                "tokens_used": self.tokens_used,
                "total_cost": round(self.total_cost, 6),
            }


_GLOBAL = Metrics()
_hook_installed = False


def get_metrics() -> Metrics:
    global _hook_installed
    if not _hook_installed:
        try:
            from logger import set_metrics_hook
        except ImportError:  # pragma: no cover
            from .logger import set_metrics_hook

        def _hook(event_type: str, payload: dict[str, Any]) -> None:
            data = payload.get("data") or {}
            sid = payload.get("session_id")
            if sid:
                _GLOBAL.start_session(str(sid))
            if event_type == "latency":
                _GLOBAL.add_latency(str(data.get("step_name")), float(data.get("ms") or 0))
            elif event_type == "tool_call":
                _GLOBAL.add_tool_call(
                    str(data.get("tool_name")),
                    float(data.get("duration_ms") or 0),
                    bool(data.get("success")),
                )
            elif event_type == "retrieval":
                _GLOBAL.add_retrieval(
                    query="x" * int(data.get("query_len") or 0),
                    hits=int(data.get("hits") or 0),
                    total=int(data.get("total_chunks") or 0),
                )
            elif event_type == "lead_score":
                _GLOBAL.add_lead_score(int(data.get("score") or 0))
            elif event_type == "escalation":
                _GLOBAL.add_escalation(str(data.get("reason") or "unknown"))
            elif event_type == "case_value":
                _GLOBAL.add_case_value(float(data.get("estimate") or 0))
            elif event_type == "tokens":
                _GLOBAL.add_tokens(int(data.get("tokens") or 0))
                if "cost" in data:
                    _GLOBAL.add_cost(float(data.get("cost") or 0))
            elif event_type == "sol_failure":
                _GLOBAL.add_sol_failure()
            elif event_type == "conflict_detected":
                _GLOBAL.add_conflict_detected()
            elif event_type == "attorney_route":
                _GLOBAL.add_attorney_route(str(data.get("attorney_key") or "unassigned"))

        set_metrics_hook(_hook)
        _hook_installed = True
    return _GLOBAL


def reset_metrics() -> Metrics:
    """Replace global metrics (tests / dashboard reset)."""
    global _GLOBAL, _hook_installed
    _GLOBAL = Metrics()
    _hook_installed = False
    return get_metrics()
