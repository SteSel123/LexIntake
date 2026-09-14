# LexIntake

Agentic RAG intake system for law firms. Prospective leads are screened for practice-area fit, jurisdiction, statute of limitations, conflicts, case value, and attorney routing — with legal guardrails and full observability.

> **This is not legal advice. Consult a licensed attorney.**

## Features

- Synthetic law-firm knowledge base (`kb/`) with multiple document types
- ETL → PostgreSQL `kb_docs` via **pgvector** (HNSW) + JSONB payloads
- Structured entities in PostgreSQL (`clients`, `attorneys`, `past_cases`)
- Agno tools: SOL check, conflict check, case value, routing
- Intake agent: plan → retrieve → **agentic tool selection** (`Agent.run`) → score → self-check → respond
- Multi-turn **Interview** tab for prospective clients
- Lead scoring engine with explicit decisions (`SCHEDULE_CONSULT` / `REVIEW` / `REJECT`)
- Monitoring: JSONL metrics + Streamlit dashboard + **Agno native tracing**
- Evaluation harness + Streamlit UI demo

## Quick start

**Requires:** Docker Desktop / Docker Compose. Copy `.env.example` → `.env` and set `OPENAI_API_KEY`.

Host-side Python commands expect the repo root on `PYTHONPATH` (set automatically by `make` targets and Docker). Optional: `pip install -e .`

```bash
make setup
# or: docker compose up --build
```

| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| Postgres | `localhost:5432` |

Stop with `make down`. Init runs once (schema seed + ETL) before API/UI start.

### Optional — local Python + Postgres only

For host-side development (edit code without rebuilding images):

```bash
make setup-local   # pip + Postgres container + schema + ETL
make ui            # Streamlit on the host
# optional: make api
```

Or manually: `docker compose up -d postgres`, then run Python commands against `DATABASE_URL=...@localhost:5432/...`.

Useful targets: `make help`, `make logs`, `make demo`, `make eval`.

### Database

PostgreSQL is **required**. LanceDB and SQLite were removed; vectors live in `kb_docs` with:

| Extension / feature | Role |
|---------------------|------|
| **pgvector** | embedding ANN (cosine / HNSW) |
| **JSONB `payload`** | type-specific fields (`faq`, `sol_rules`, …) |
| **`text[]` jurisdictions** | GIN-filtered metadata |
| **pg_trgm** | optional fuzzy text search |

Default URL (docker compose):

```
DATABASE_URL=postgresql://lexintake:lexintake@localhost:5432/lexintake
```

### Provider configuration (`.env`)

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | *(required)* PostgreSQL URL |
| `LEXINTAKE_EMBEDDING_PROVIDER` | `openai` |
| `LEXINTAKE_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `LEXINTAKE_LLM_PROVIDER` | `openai` |
| `LEXINTAKE_LLM_MODEL` | `gpt-4.1` |
| `OPENAI_API_KEY` | *(required)* |

## Repository layout

| Path | Purpose |
|------|---------|
| `kb/` | Knowledge base sources |
| `etl/` | Extract → transform → embed → load into Postgres |
| `db/` | SQLAlchemy models, Alembic, `pgvector_store.py` |
| `Dockerfile` / `docker-compose.yml` | Full stack: Postgres + init + API + UI |
| `Makefile` | `make setup` (default Docker stack) / `make setup-local` |
| `tools/` | Agno tools |
| `agents/` | Intake and interview agents |
| `scoring/` | Lead scoring engine |
| `monitoring/` | JSONL logger, metrics, Streamlit dashboard |
| `evaluation/` | Labeled leads, metrics, runner |
| `frontend/` | Streamlit intake UI + demo scenarios |
| `backend/` | FastAPI REST API |
| `tests/` | Pytest unit tests (deterministic modules) |
| `docs/` | Design report, evaluation report, demo script |

## Agent loop

```text
Plan → Retrieve (Postgres kb_docs / pgvector) → Tools → Decision / Scoring → Self-check → Respond
```

## Guardrails

Every user-facing response includes:

1. Legal disclaimer
2. No prescriptive legal advice
3. KB citations (`chunk_id`, `practice_area`, `doc_type`)
4. Escalation when uncertain
5. No invented statutes / SOL / attorney profiles

## License

Educational capstone project.
