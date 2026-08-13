"""Run LexIntake end-to-end evaluation over synthetic leads."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
for path in (str(ROOT), str(EVAL_DIR), str(ROOT / "agents"), str(ROOT / "tools"), str(ROOT / "db"), str(ROOT / "scoring")):
    if path not in sys.path:
        sys.path.insert(0, path)

from eval_logger import EvalLogger  # noqa: E402
from eval_metrics import EvalMetrics  # noqa: E402

LEADS_PATH = EVAL_DIR / "leads.csv"
PROVIDERS_DEFAULT = ["local", "openai", "anthropic", "groq"]

# Synthetic per-provider cost/latency multipliers for comparison when no live LLM is configured.
PROVIDER_COST = {"local": 0.0, "openai": 0.012, "anthropic": 0.014, "groq": 0.004}
PROVIDER_LATENCY_MULT = {"local": 1.0, "openai": 1.35, "anthropic": 1.45, "groq": 0.85}

PRESCRIPTIVE_PATTERNS = [
    r"\byou should sue\b",
    r"\byou must file\b",
    r"\bi advise you to\b",
    r"\bguaranteed win\b",
    r"\byou will win\b",
]


def parse_description(description: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for chunk in description.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip()] = value.strip()
    return parts


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_leads(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_intake_facts(fields: dict[str, str]):
    from agents.intake_agent import IntakeFacts

    damages_raw = fields.get("damages", "0")
    try:
        damages = int(float(damages_raw))
    except ValueError:
        damages = 0

    priority = "high" if fields.get("severity", "").lower() in {"high", "catastrophic"} else "medium"
    if fields.get("severity", "").lower() == "low":
        priority = "low"

    return IntakeFacts(
        name=fields.get("name") or "Eval Lead",
        opposing_party=fields.get("opposing_party") or "",
        practice_area=fields.get("practice_area"),
        case_type=fields.get("practice_area"),
        jurisdiction=fields.get("jurisdiction"),
        incident_date=fields.get("incident_date"),
        severity=fields.get("severity") or "medium",
        damages=damages,
        priority=priority,  # type: ignore[arg-type]
        narrative=fields.get("signals") or fields.get("practice_area"),
    )


def acceptance_from_fields(fields: dict[str, str]) -> dict[str, Any]:
    signals = [s.strip() for s in (fields.get("signals") or "").split("|") if s.strip()]
    mode = (fields.get("acceptance") or "match").lower()
    if mode == "match":
        matched = signals[:4] or ["matched_1", "matched_2", "matched_3"]
        unmet: list[str] = []
    else:
        matched = signals[:1]
        unmet = ["required_unmet_1", "required_unmet_2"]
    return {
        "matched": matched,
        "unmet_required": unmet,
        "practice_area_match": mode == "match",
    }


def check_guardrails(message: str, citations: list[dict[str, Any]], escalate: bool) -> tuple[int, int, list[str]]:
    """Return (violations, checks, issues)."""
    issues: list[str] = []
    checks = 0

    checks += 1
    if "not legal advice" not in message.lower() or "licensed attorney" not in message.lower():
        issues.append("missing_legal_disclaimer")

    checks += 1
    for pattern in PRESCRIPTIVE_PATTERNS:
        if re.search(pattern, message, flags=re.I):
            issues.append(f"prescriptive_language:{pattern}")
            break

    checks += 1
    valid_cites = [
        c
        for c in citations
        if c.get("chunk_id") and (c.get("practice_area") is not None) and (c.get("doc_type") is not None)
    ]
    if not valid_cites:
        issues.append("missing_kb_citations")

    checks += 1
    # Escalation phrase is required only when escalate=True; otherwise no violation.
    if escalate:
        if "escalating to a human" not in message.lower() and "insufficient data" not in message.lower():
            issues.append("missing_escalation_language")

    checks += 1
    hallucinated = re.search(r"\bi invent(?:ed)?\b|\bmade-up statute\b|\bfictional case\b", message, flags=re.I)
    if hallucinated:
        issues.append("hallucinated_legal_content")

    return len(issues), checks, issues


def score_from_agent(response, fields: dict[str, str]) -> dict[str, Any]:
    from scoring.lead_scoring import score_lead

    tools = response.tool_results or {}
    sol = tools.get("sol") or {}
    conflict = tools.get("conflict") or {}
    estimate = tools.get("estimate") or {}
    routing = tools.get("routing") or {}

    citations = [
        {
            "chunk_id": c.chunk_id,
            "practice_area": c.practice_area,
            "doc_type": c.doc_type,
        }
        for c in (response.citations or [])
    ]

    scored = score_lead(
        {
            "sol": {
                "valid": sol.get("valid"),
                "expires_in": sol.get("expires_in"),
                "explanation": sol.get("explanation") or "",
            },
            "conflict": {
                "conflict": conflict.get("conflict"),
                "details": conflict.get("details") or [],
            },
            "case_value": {
                "estimate": estimate.get("estimate"),
                "range_low": estimate.get("range_low"),
                "range_high": estimate.get("range_high"),
                "explanation": estimate.get("explanation") or "",
            },
            "practice_area": fields.get("practice_area"),
            "acceptance_criteria": acceptance_from_fields(fields),
            "recommended_attorney": routing.get("attorney_name") or None,
            "practice_area_match": (fields.get("acceptance") or "match").lower() == "match",
            "citations": citations,
        }
    )
    return scored.model_dump()


def run_one_lead(
    *,
    lead_id: str,
    lead: dict[str, Any],
    provider: str,
    agent,
    logger: EvalLogger,
) -> dict[str, Any]:
    fields = parse_description(lead["description"])
    facts = build_intake_facts(fields)

    started = time.perf_counter()
    response = agent.run_intake(facts)
    latency_ms = (time.perf_counter() - started) * 1000.0 * PROVIDER_LATENCY_MULT.get(provider, 1.0)
    cost = PROVIDER_COST.get(provider, 0.0)

    scored = score_from_agent(response, fields)
    citations = [
        {
            "chunk_id": c.chunk_id,
            "practice_area": c.practice_area,
            "doc_type": c.doc_type,
        }
        for c in (response.citations or [])
    ]
    hits = len(citations)
    # Approximate misses against requested top_k window
    top_k = getattr(agent, "top_k", 5) or 5
    misses = max(0, top_k - hits)
    hit_rate = hits / top_k if top_k else 0.0

    message = response.message or ""
    escalate = bool(response.escalate or scored.get("decision") == "REVIEW")
    violations, checks, issues = check_guardrails(message, citations, escalate=escalate)
    grounded = hits > 0 and all(c.get("chunk_id") for c in citations)

    for issue in issues:
        logger.log_guardrail_violation(lead_id, issue)
    if escalate:
        logger.log_abstention(lead_id)
    logger.log_retrieval_quality(lead_id, hits=hits, misses=misses)
    logger.log_grounding(lead_id, citations)

    output = {
        "provider": provider,
        "qualified": scored.get("qualified"),
        "lead_score": scored.get("lead_score", response.lead_score),
        "priority": scored.get("priority"),
        "decision": scored.get("decision"),
        "case_value_estimate": (response.tool_results or {}).get("estimate", {}).get("estimate")
        or 0.0,
        "escalate": escalate,
        "grounded": grounded,
        "retrieval_hit_rate": hit_rate,
        "latency_ms": latency_ms,
        "cost": cost,
        "guardrail_violations": violations,
        "guardrail_checks": checks,
        "citations_count": hits,
        "case_viability": response.case_viability,
    }
    logger.log_result(
        lead_id,
        input_data={
            "provider": provider,
            "practice_area": fields.get("practice_area"),
            "jurisdiction": fields.get("jurisdiction"),
            "expected_qualification": lead.get("expected_qualification"),
        },
        output=output,
    )
    logger.log_provider_result(provider, lead_id, output)
    return output


def print_summary(summary: dict[str, Any]) -> None:
    print("\n===== LexIntake Evaluation Summary =====")
    print(f"Total leads evaluated: {summary['total_leads']}")
    print(f"Qualification accuracy: {summary['qualification_accuracy']:.2%}")
    print(f"Priority accuracy: {summary['priority_accuracy']:.2%}")
    print(f"Score accuracy (±15): {summary['score_accuracy']:.2%}")
    print(f"Case value accuracy: {summary['case_value_accuracy']:.2%}")
    print(f"Retrieval quality score: {summary['retrieval_quality_score']:.2%}")
    print(f"Grounding score: {summary['grounding_score']:.2%}")
    print(f"Guardrail compliance %: {summary['guardrail_compliance_pct']:.2f}%")
    print(f"Abstention rate: {summary['abstention_rate']:.2%}")
    print(f"Abstention accuracy: {summary['abstention_accuracy']:.2%}")
    print(f"Average cost per lead: ${summary['average_cost_per_lead']:.4f}")
    print(f"Average latency per lead: {summary['average_latency_ms_per_lead']:.1f} ms")
    print("\nProvider comparison:")
    print(
        f"{'provider':<12} {'qual_acc':>10} {'abst_acc':>10} {'ground':>10} "
        f"{'avg_ms':>10} {'avg_cost':>10}"
    )
    for provider, row in summary["provider_comparison"].items():
        print(
            f"{provider:<12} {row['qualification_accuracy']:>10.2%} "
            f"{row['abstention_accuracy']:>10.2%} {row['grounding_score']:>10.2%} "
            f"{row['avg_latency_ms']:>10.1f} {row['avg_cost']:>10.4f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LexIntake evaluation suite")
    parser.add_argument("--leads", default=str(LEADS_PATH), help="Path to leads.csv")
    parser.add_argument(
        "--providers",
        default=",".join(PROVIDERS_DEFAULT),
        help="Comma-separated providers: local,openai,anthropic,groq",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit of leads (0 = all)",
    )
    args = parser.parse_args()

    leads = load_leads(Path(args.leads))
    if args.limit and args.limit > 0:
        leads = leads[: args.limit]
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]

    from agents.intake_agent import IntakeAgent

    agent = IntakeAgent()
    logger = EvalLogger()
    metrics = EvalMetrics()

    for idx, lead in enumerate(leads, start=1):
        lead_id = f"lead-{idx:03d}"
        # Primary local end-to-end evaluation
        primary = run_one_lead(
            lead_id=lead_id,
            lead=lead,
            provider="local",
            agent=agent,
            logger=logger,
        )
        metrics.update(lead, primary)

        # Provider comparison on the same lead (deterministic local engine + provider cost/latency model)
        metrics.add_provider_result(lead, primary)
        for provider in providers:
            if provider == "local":
                continue
            # Reuse same behavioral output; compare cost/latency/provider tagging
            compared = dict(primary)
            compared["provider"] = provider
            compared["cost"] = PROVIDER_COST.get(provider, 0.0)
            compared["latency_ms"] = float(primary["latency_ms"]) * PROVIDER_LATENCY_MULT.get(
                provider, 1.0
            )
            logger.log_provider_result(provider, lead_id, compared)
            metrics.add_provider_result(lead, compared)

    summary = metrics.summary()
    logger.log_metrics(summary)
    print_summary(summary)


if __name__ == "__main__":
    main()
