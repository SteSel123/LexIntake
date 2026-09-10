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
                    ┌────────────────┐         ┌──────────────────┐
   Case description │   frontend/    │  HTTP   │  backend/api     │
         ──────────►│  Streamlit UI  │────────►│  FastAPI         │
                    └───────┬────────┘         └────────┬─────────┘
                            │ in-process                │
                            │ (demo / CLI)              │
                    ┌───────▼───────────────────────────▼─────────┐
                    │         backend/services (intake)            │
                    └───────────────────┬─────────────────────────┘
                                        │
                               ┌────────▼────────┐
                               │   IntakeAgent   │  plan / retrieve / tools / decide / self-check
                               └────────┬────────┘
                      ┌─────────────────┼────────────────┐
                      ▼                 ▼                ▼
                Postgres kb_docs   Agno Tools       Lead Scoring
                (pgvector RAG)     (SOL/conflict/   (qualified, score,
                                    value/route)     priority, decision)
                      ▲                 ▲
                      │                 │
                   ETL pipeline      Postgres entities
                   kb/ → chunks      clients/attorneys/cases
```

### Components

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Agent framework | Agno | Tool decorator + Agent base class; reasoning + tool_choice |
| Vector DB | PostgreSQL + pgvector | Heterogeneous KB chunks, HNSW cosine, JSONB payloads |
| Structured DB | PostgreSQL + SQLAlchemy + Alembic | Shared DB for entities + vectors; versioned schema |
| Embeddings | OpenAI `text-embedding-3-small` | Semantic RAG; requires `OPENAI_API_KEY` |
| LLM | OpenAI `gpt-4.1` (Anthropic/Groq optional for eval) | Planning refine + narrative explanations |
| Backend API | FastAPI | Clear HTTP surface + OpenAPI docs for intake/interview |
| Frontend | Streamlit | Fast demo surface over shared services |
| Monitoring | Custom JSONL + Streamlit + **Agno tracing** | Capstone metrics + native Agno spans |
| CI | GitHub Actions `smoke-test` | PR checks to `main`; Postgres service + live OpenAI ETL + eval `--limit 5` |

## 4. Knowledge base

Synthetic firm KB under `kb/`:

- practice areas, acceptance criteria, fee structure
- SOL tables, past cases, attorneys, clients, FAQs

Designed for grounding intake decisions and conflict/value checks.

## 5. ETL design

Pipeline stages live under `etl/`:

- **extract/** — read and flatten `kb/` into document records
- **transform/** — clean → deduplicate → chunk → metadata → embeddings
- **load/** — upsert into PostgreSQL `kb_docs` (pgvector)

Properties:

- **Re-runnable:** safe to execute repeatedly
- **Idempotent:** stable `content_hash` / `chunk_id`; Postgres `ON CONFLICT` upsert
- **Incremental:** unchanged chunks can reuse embeddings; upsert retains prior rows

## 6. Agent workflow

1. **Plan** — missing fields, tools, retrieval need, escalation flags (LLM can refine tool selection)  
2. **Retrieve** — pgvector semantic search filtered by practice area / jurisdiction / doc type  
3. **Tools** — SOL, conflict, estimate, route  
4. **Decision / scoring** — viability + `score_lead()` decision object  
5. **Self-check** — disclaimer, citations, unsafe language, confidence  
6. **Respond** — LLM narrative with template fallback if a completion fails; always enforce guardrails

## 7. Tools

| Tool | Source | Purpose |
|------|--------|---------|
| `check_statute_of_limitations` | `sol_tables.json` | Deadline validity |
| `conflict_check` | Postgres `clients` | Conflict screening |
| `estimate_case_value` | `past_cases` (+ vector fallback) | Settlement estimate |
| `route_lead` | Postgres attorneys + caseload | Attorney assignment |

## 8. Guardrails

Mandatory in every response:

1. Legal disclaimer (“This is not legal advice…”)
2. No prescriptive legal advice
3. Cite KB evidence (`chunk_id`, `practice_area`, `doc_type`)
4. Escalate when uncertain / conflicting / low confidence
5. Refuse invented statutes, SOL rules, case law, attorney profiles

## 9. Observability

Tracked per session:

- tokens / cost
- latency per phase
- tool call success/duration
- retrieval hit rate
- lead score + case value distributions
- escalation rate

Dashboard: `python -m streamlit run monitoring/dashboard.py`

CI workflow: `.github/workflows/ci.yml` (OpenAI embeddings + LLM; requires `OPENAI_API_KEY` secret).

## 10. Evaluation strategy

Labeled set (`evaluation/leads.csv`, ~30 leads) measures:

1. Retrieval quality  
2. Grounding  
3. Qualification accuracy  
4. Case valuation  
5. Abstention behavior  
6. Guardrails  
7. Cost & latency  
8. Provider comparison (`openai` / `anthropic` / `groq` when keys present)

Details: [EVALUATION_REPORT.md](EVALUATION_REPORT.md)

## 11. Git workflow (capstone)

- `main` — protected production tip (requires `smoke-test` CI)  
- `develop` — integration  
- `feature/*` — scoped work (kb, etl, database, tools, agent, scoring, monitoring, evaluation, ui, openai/ci)

Pull requests are used for instructor review. Clean commits map to feature areas.

## 12. Risks & limitations

- Multi-turn conversational interview is available in the Streamlit **Interview** tab (`agents/interview/`).
- Runtime always uses **OpenAI embeddings + gpt-4.1** (or another configured live LLM). `OPENAI_API_KEY` is required.
- Observability uses custom JSONL metrics **and** Agno native tracing (`monitoring/agno_tracing.py` → `monitoring/traces.db`).
- Case-value estimates depend on sparse synthetic comps; valuation accuracy is limited.
- Conflict detection is name-similarity based, not full conflict-of-interest counsel.
- Not a substitute for licensed attorney review.

## 13. Stretch goals (not in MVP)

- Corrective RAG
- Multi-agent team
- Rich human-in-the-loop console
- Persistent memory
- Nightly full evaluation / live multi-provider bakeoffs in CI