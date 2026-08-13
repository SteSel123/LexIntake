# LexIntake Design Report

## 1. Problem

Law firms receive high volumes of inbound leads. Paralegals spend significant time filtering:

- wrong practice area
- wrong jurisdiction
- expired statutes of limitations (SOL)
- conflicts of interest
- low-value matters

LexIntake automates first-pass screening with an **agentic RAG** workflow: plan → retrieve → tools → score → self-check → respond.

## 2. Goals & non-goals

**Goals**

- Deterministic screening where possible (SOL, conflicts, scoring rules)
- Retrieval-grounded explanations with KB citations
- Explicit lead decisions: `SCHEDULE_CONSULT` / `REVIEW` / `REJECT`
- Observability (latency, tool calls, retrieval hit rate, escalations)
- Evaluation harness over labeled synthetic leads

**Non-goals**

- Providing legal advice
- Replacing attorney judgment
- Full case management / CRM replacement

## 3. Architecture

```text
                    ┌─────────────┐
   Case description │  Streamlit  │
         ──────────►│   ui/app    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ IntakeAgent │  plan / retrieve / tools / decide / self-check
                    └──────┬──────┘
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
     LanceDB kb_docs   Agno Tools      Lead Scoring
     (vector RAG)      (SOL/conflict/  (qualified, score,
                        value/route)    priority, decision)
           ▲               ▲
           │               │
        ETL pipeline    SQLite entities
        kb/ → chunks    clients/attorneys/cases
```

### Components

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Agent framework | Agno | Tool decorator + Agent base class |
| Vector DB | LanceDB | Local, upsert by `chunk_id`, good for demos |
| Structured DB | SQLite | Zero-ops local entities + FK relations |
| Embeddings (current) | Deterministic hash embedder | Offline/reproducible; provider-ready interface |
| UI | Streamlit | Fast demo surface |
| Monitoring | Custom JSONL + Streamlit | Captures required metrics without cloud lock-in |

## 4. Knowledge base

Synthetic firm KB under `kb/`:

- practice areas, acceptance criteria, fee structure
- SOL tables, past cases, attorneys, clients, FAQs

Designed for grounding intake decisions and conflict/value checks.

## 5. ETL design

Pipeline steps: extract → clean → deduplicate → chunk → metadata → embeddings → load.

Properties:

- **Re-runnable:** safe to execute repeatedly
- **Idempotent:** stable `content_hash` / `chunk_id`; LanceDB `merge_insert`
- **Incremental:** unchanged chunks can reuse embeddings; upsert retains prior rows

## 6. Agent workflow

1. **Plan** — missing fields, tools, retrieval need, escalation flags  
2. **Retrieve** — LanceDB search filtered by practice area / jurisdiction / doc type  
3. **Tools** — SOL, conflict, estimate, route, optional fallback  
4. **Decision / scoring** — viability + `score_lead()` decision object  
5. **Self-check** — disclaimer, citations, unsafe language, confidence  
6. **Respond** — user message + structured JSON for UI/eval  

## 7. Tools

| Tool | Source | Purpose |
|------|--------|---------|
| `check_statute_of_limitations` | `sol_tables.json` | Deadline validity |
| `conflict_check` | SQLite `clients` | Conflict screening |
| `estimate_case_value` | `past_cases` (+ vector fallback) | Settlement estimate |
| `route_lead` | SQLite attorneys + caseload | Attorney assignment |
| `web_search_fallback` | Local KB only | Offline fallback marker |

## 8. Guardrails

Mandatory in every response:

1. Legal disclaimer (“This is not legal advice…”)
2. No prescriptive legal advice
3. Cite KB evidence (`chunk_id`, `practice_area`, `doc_type`)
4. Escalate when uncertain / conflicting / low confidence
5. Refuse invented statutes, SOL rules, case law, attorney profiles

## 9. Observability

Tracked per session:

- tokens / cost (hooks ready; local path currently ~$0)
- latency per phase
- tool call success/duration
- retrieval hit rate
- lead score + case value distributions
- escalation rate

Dashboard: `python -m streamlit run monitoring/dashboard.py`

## 10. Evaluation strategy

Labeled set (`evaluation/leads.csv`, ~30 leads) measures:

1. Retrieval quality  
2. Grounding  
3. Qualification accuracy  
4. Case valuation  
5. Abstention behavior  
6. Guardrails  
7. Cost & latency  
8. Provider comparison (local baseline + modeled provider costs)

Details: [EVALUATION_REPORT.md](EVALUATION_REPORT.md)

## 11. Git workflow (capstone)

- `main` — protected production tip  
- `develop` — integration  
- `feature/*` — scoped work (kb, etl, database, tools, agent, scoring, monitoring, evaluation, ui)

Pull requests are used for instructor review. Clean commits map to feature areas.

## 12. Risks & limitations

- Current default path is **deterministic / offline** (hash embeddings, no live LLM). Real provider RAG is a planned upgrade.
- Case-value estimates depend on sparse synthetic comps; valuation accuracy is limited.
- Conflict detection is name-similarity based, not full conflict-of-interest counsel.
- Not a substitute for licensed attorney review.

## 13. Stretch goals (not in MVP)

- Corrective RAG
- Multi-agent team
- Rich human-in-the-loop console
- Persistent memory
- Full CI/CD + live multi-provider eval
