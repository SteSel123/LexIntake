# LexIntake Demo Guide

Capstone deliverable: demo of the working system.  
Use this script to record a **3–5 minute demo video**.

> On-screen disclaimer to show first:  
> **This is not legal advice. Consult a licensed attorney.**

## Prerequisites

```powershell
pip install -r requirements.txt
python db/init_structured_db.py
python -m etl.pipeline
```

## Recording outline (suggested)

### 0:00–0:20 — Problem & thesis

- Law firms drown in inbound leads.
- LexIntake is an **agentic RAG intake screener**, not a chatbot.
- Loop: plan → retrieve → tools → score → self-check.

### 0:20–0:50 — Repo & architecture

Show briefly:

- `kb/` knowledge base
- `etl/extract`, `etl/transform`, `etl/load` pipeline
- `db/` LanceDB + SQLite
- `agents/` + `tools/` + `scoring/`
- `monitoring/` + `evaluation/` + `ui/`

### 0:50–2:40 — Live UI demo

```powershell
python -m streamlit run ui/app.py
```

Run these sidebar examples:

1. **Valid Personal Injury**  
   Expect: qualified, High, `SCHEDULE_CONSULT`, attorney + citations.

2. **SOL Expired**  
   Expect: `REJECT`, explanation mentions SOL.

3. **Conflict Case**  
   Expect: conflict / reject + escalation banner.

4. **Uncertain / Review**  
   Expect: `REVIEW` + “Escalated to human intake specialist.”

Point out on every result:

- disclaimer
- KB citations (`chunk_id`, `practice_area`, `doc_type`)
- raw JSON decision object

### 2:40–3:20 — Observability

```powershell
python -m streamlit run monitoring/dashboard.py
```

Click **Load demo metrics** (or run UI analysis first). Show latency, tool usage, lead-score distribution, escalations.

### 3:20–4:00 — Evaluation

```powershell
python evaluation/run_evaluation.py --limit 10
```

Show summary metrics and mention full report in `docs/EVALUATION_REPORT.md`.

### 4:00–4:30 — Close

- Guardrails are mandatory.
- Human attorney remains final authority.
- Stretch: live multi-provider LLM + CI/CD.

## CLI alternative (no video UI)

```powershell
python ui/demo.py
```

Expected: `Demo complete: 4/4 scenarios passed`.

## Upload checklist

- [ ] Video shows disclaimer  
- [ ] At least 3 UI scenarios  
- [ ] Citations visible  
- [ ] Escalation visible  
- [ ] Mentions evaluation/monitoring  
- [ ] Link video in README (YouTube/Drive/Loom)
