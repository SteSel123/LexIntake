"""Evaluation metrics collector for LexIntake."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _parse_range(value: str | float | int) -> tuple[float, float]:
    if isinstance(value, (int, float)):
        v = float(value)
        return v, v
    text = str(value or "").strip()
    if "-" in text:
        left, right = text.split("-", 1)
        return float(left.strip() or 0), float(right.strip() or 0)
    num = float(text or 0)
    return num, num


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


@dataclass
class EvalMetrics:
    total_leads: int = 0
    correct_qualification: int = 0
    correct_priority: int = 0
    correct_score_range: int = 0
    correct_case_value: int = 0
    correct_abstention: int = 0
    guardrail_violations: int = 0
    guardrail_checks: int = 0
    abstentions: int = 0
    expected_abstentions: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    costs: list[float] = field(default_factory=list)
    retrieval_hit_rates: list[float] = field(default_factory=list)
    grounded_responses: int = 0
    provider_rows: list[dict[str, Any]] = field(default_factory=list)
    provider_comparison: dict[str, Any] = field(default_factory=dict)

    def update(self, lead: dict[str, Any], agent_output: dict[str, Any]) -> None:
        self.total_leads += 1

        expected_qual = _as_bool(lead.get("expected_qualification"))
        expected_priority = str(lead.get("expected_priority") or "").strip()
        expected_score = float(lead.get("expected_score") or 0)
        expected_escalation = _as_bool(lead.get("expected_escalation"))
        low, high = _parse_range(lead.get("expected_case_value", "0-0"))

        got_qual = _as_bool(agent_output.get("qualified"))
        got_priority = str(agent_output.get("priority") or "").strip()
        got_score = float(agent_output.get("lead_score") or 0)
        got_estimate = float(agent_output.get("case_value_estimate") or 0)
        got_escalate = _as_bool(agent_output.get("escalate"))

        if got_qual == expected_qual:
            self.correct_qualification += 1
        if got_priority == expected_priority:
            self.correct_priority += 1
        if abs(got_score - expected_score) <= 15:
            self.correct_score_range += 1
        if low <= got_estimate <= high:
            self.correct_case_value += 1

        if expected_escalation:
            self.expected_abstentions += 1
        if got_escalate:
            self.abstentions += 1
        if got_escalate == expected_escalation:
            self.correct_abstention += 1

        violations = int(agent_output.get("guardrail_violations") or 0)
        checks = int(agent_output.get("guardrail_checks") or 0)
        self.guardrail_violations += violations
        self.guardrail_checks += max(checks, 1)

        if agent_output.get("grounded"):
            self.grounded_responses += 1

        if "latency_ms" in agent_output:
            self.latencies_ms.append(float(agent_output["latency_ms"]))
        if "cost" in agent_output:
            self.costs.append(float(agent_output["cost"]))
        if "retrieval_hit_rate" in agent_output:
            self.retrieval_hit_rates.append(float(agent_output["retrieval_hit_rate"]))

    def add_provider_result(self, lead: dict[str, Any], agent_output: dict[str, Any]) -> None:
        """Track provider comparison without double-counting primary lead accuracy."""
        expected_qual = _as_bool(lead.get("expected_qualification"))
        expected_escalation = _as_bool(lead.get("expected_escalation"))
        got_qual = _as_bool(agent_output.get("qualified"))
        got_escalate = _as_bool(agent_output.get("escalate"))
        provider = str(agent_output.get("provider") or "local")
        self.provider_rows.append(
            {
                "provider": provider,
                "qualification_correct": got_qual == expected_qual,
                "abstention_correct": got_escalate == expected_escalation,
                "grounded": bool(agent_output.get("grounded")),
                "latency_ms": float(agent_output.get("latency_ms") or 0),
                "cost": float(agent_output.get("cost") or 0),
            }
        )

    def compute_accuracy(self) -> dict[str, float]:
        n = max(1, self.total_leads)
        return {
            "qualification_accuracy": self.correct_qualification / n,
            "priority_accuracy": self.correct_priority / n,
            "score_accuracy": self.correct_score_range / n,
            "case_value_accuracy": self.correct_case_value / n,
            "abstention_accuracy": self.correct_abstention / n,
        }

    def compute_guardrail_score(self) -> float:
        checks = max(1, self.guardrail_checks)
        compliance = 1.0 - (self.guardrail_violations / checks)
        return max(0.0, min(1.0, compliance))

    def compute_abstention_rate(self) -> float:
        n = max(1, self.total_leads)
        return self.abstentions / n

    def compute_cost(self) -> float:
        if not self.costs:
            return 0.0
        return sum(self.costs) / len(self.costs)

    def compute_latency(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def compute_retrieval_quality(self) -> float:
        if not self.retrieval_hit_rates:
            return 0.0
        return sum(self.retrieval_hit_rates) / len(self.retrieval_hit_rates)

    def compute_grounding(self) -> float:
        n = max(1, self.total_leads)
        return self.grounded_responses / n

    def compute_provider_comparison(self) -> dict[str, Any]:
        by_provider: dict[str, list[dict[str, Any]]] = {}
        for row in self.provider_rows:
            by_provider.setdefault(row["provider"], []).append(row)

        comparison: dict[str, Any] = {}
        for provider, rows in sorted(by_provider.items()):
            n = max(1, len(rows))
            comparison[provider] = {
                "leads": len(rows),
                "qualification_accuracy": sum(1 for r in rows if r["qualification_correct"]) / n,
                "abstention_accuracy": sum(1 for r in rows if r["abstention_correct"]) / n,
                "grounding_score": sum(1 for r in rows if r["grounded"]) / n,
                "avg_latency_ms": sum(r["latency_ms"] for r in rows) / n,
                "avg_cost": sum(r["cost"] for r in rows) / n,
            }
        self.provider_comparison = comparison
        return comparison

    def summary(self) -> dict[str, Any]:
        acc = self.compute_accuracy()
        return {
            "total_leads": self.total_leads,
            "qualification_accuracy": round(acc["qualification_accuracy"], 4),
            "priority_accuracy": round(acc["priority_accuracy"], 4),
            "score_accuracy": round(acc["score_accuracy"], 4),
            "case_value_accuracy": round(acc["case_value_accuracy"], 4),
            "retrieval_quality_score": round(self.compute_retrieval_quality(), 4),
            "grounding_score": round(self.compute_grounding(), 4),
            "guardrail_compliance_pct": round(self.compute_guardrail_score() * 100.0, 2),
            "abstention_rate": round(self.compute_abstention_rate(), 4),
            "abstention_accuracy": round(acc["abstention_accuracy"], 4),
            "average_cost_per_lead": round(self.compute_cost(), 6),
            "average_latency_ms_per_lead": round(self.compute_latency(), 3),
            "provider_comparison": self.compute_provider_comparison(),
        }
