# LexIntake

Agentic RAG intake system for law firms. Prospective leads are screened for practice-area fit, jurisdiction, statute of limitations, conflicts, case value, and attorney routing — with legal guardrails and full observability.

> **This is not legal advice. Consult a licensed attorney.**

## Features

- Synthetic law-firm knowledge base (`kb/`)
- Re-runnable / idempotent / incremental ETL → LanceDB
- Structured entities in SQLite (`clients`, `attorneys`, `past_cases`)
- Agno tools: SOL check, conflict check, case value, routing, fallback
- Intake agent: plan → retrieve → **agentic tool selection** (`Agent.run`) → score → self-check → respond  
- Multi-turn **Interview** tab for prospective clients  
- Lead scoring engine with explicit decisions (`SCHEDULE_CONSULT` / `REVIEW` / `REJECT`)  
- Monitoring: JSONL metrics + Streamlit dashboard + **Agno native tracing**  
- Evaluation harness + Streamlit UI demo

## Quick start

```powershell
# Python 3.11+ recommended
pip install -r requirements.txt

# Configure providers (never commit real keys)
copy .env.example .env
# Edit .env and set OPENAI_API_KEY=...

# Structured DB + seed from kb/
python db/init_structured_db.py

# ETL → LanceDB kb_docs (OpenAI text-embedding-3-small by default)
python db/load_kb_docs.py
# or
python etl/load_vector_db.py

# UI demo
python -m streamlit run ui/app.py

# Monitoring dashboard
python -m streamlit run monitoring/dashboard.py

# Evaluation with live provider comparison (skips missing API keys)
python evaluation/run_evaluation.py --limit 5

# Scenario demo (CLI)
python ui/demo.py
```

### Provider configuration (`.env`)

| Variable | Default |
|----------|---------|
| `LEXINTAKE_EMBEDDING_PROVIDER` | `openai` |
| `LEXINTAKE_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `LEXINTAKE_LLM_PROVIDER` | `openai` |
| `LEXINTAKE_LLM_MODEL` | `gpt-4.1` |
| `OPENAI_API_KEY` | *(required for live embeddings/LLM)* |
| `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | optional eval comparison |

## Repository layout

| Path | Purpose |
|------|---------|
| `kb/` | Knowledge base (practice areas, SOL, fees, cases, attorneys, clients, FAQs) |
| `etl/` | Extract → clean → dedupe → chunk → metadata → embed → load |
| `db/` | LanceDB vector store + SQLite schema/seed |
| `tools/` | Agno tools |
| `agents/` | Intake agent |
| `scoring/` | Lead scoring engine |
| `monitoring/` | JSONL logger, metrics, Streamlit dashboard |
| `evaluation/` | Labeled leads, metrics, runner |
| `ui/` | Streamlit intake UI + demo scenarios |
| `docs/` | Design report, evaluation report, demo script |

## Agent loop

```text
Plan → Retrieve (LanceDB kb_docs) → Tools → Decision / Scoring → Self-check → Respond
```

## Guardrails

Every user-facing response includes:

1. Legal disclaimer  
2. No prescriptive legal advice  
3. KB citations (`chunk_id`, `practice_area`, `doc_type`)  
4. Escalation when uncertain  
5. No invented statutes / SOL / attorney profiles  

## Git workflow

| Branch | Purpose |
|--------|---------|
| `main` | Protected production (requires CI `smoke-test`) |
| `develop` | Integration |
| `feature/*` | Individual features |

CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs offline hash embeddings + demo + eval `--limit 5` on PRs to `main`.

See [docs/DESIGN_REPORT.md](docs/DESIGN_REPORT.md) and [docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md).  
Demo recording script: [docs/DEMO.md](docs/DEMO.md).  
Full Dutch learning PDF (40+ pages): [docs/LexIntake_Leerboek.pdf](docs/LexIntake_Leerboek.pdf)  
(regenerate with `python docs/generate_leerboek_pdf.py`).

## License

Educational capstone project.
