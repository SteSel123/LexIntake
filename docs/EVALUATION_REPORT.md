# LexIntake Evaluation Report

**Date:** 2026-08-13  
**Harness:** `python evaluation/run_evaluation.py`  
**Dataset:** `evaluation/leads.csv` (30 labeled synthetic leads)  
**Stack under test:** local deterministic IntakeAgent + LanceDB + SQLite + lead scoring  

> This report evaluates screening behavior. **This is not legal advice.**

## 1. Setup

1. Seed SQLite: `python db/init_structured_db.py`  
2. Load vectors: `python db/load_kb_docs.py`  
3. Run eval: `python evaluation/run_evaluation.py`  

Metrics are logged to `evaluation/logs/evaluation.jsonl`.

## 2. Headline results (local provider)

| Metric | Result |
|--------|--------|
| Total leads | 30 |
| Qualification accuracy | 50.00% |
| Priority accuracy | 46.67% |
| Score accuracy (±15) | 33.33% |
| Case value accuracy | 36.67% |
| Retrieval quality score | 87.33% |
| Grounding score | **100.00%** |
| Guardrail compliance | **100.00%** |
| Abstention rate | 60.00% |
| Abstention accuracy | 36.67% |
| Avg cost / lead (local) | $0.0000 |
| Avg latency / lead | ~88 ms |

## 3. Dimension analysis

### 3.1 Retrieval quality

Retrieval hit rate against requested top‑k is strong (**~87%**). Filtered LanceDB queries usually return practice-area–relevant chunks (acceptance criteria, SOL, past cases).

**Interpretation:** retrieval infrastructure is healthy for demo/capstone use.

### 3.2 Grounding

**100%** of evaluated responses included KB citations with `chunk_id` / `practice_area` / `doc_type`.

**Interpretation:** citation guardrail is consistently enforced.

### 3.3 Qualification & priority accuracy

Moderate (~47–50%). Mismatches come from:

- label expectations vs deterministic scoring thresholds
- conflict hits on seeded client names in synthetic leads
- SOL parsing approximations (first duration token in free-text rules)
- incomplete intakes mapped to REVIEW/REJECT differently than labels

**Improvement path:** calibrate `score_lead` thresholds and label set jointly; enrich SOL structured fields (numeric years) instead of free text only.

### 3.4 Case valuation

**~37%** within labeled ranges. Estimates blend comparable settlements with stated damages; synthetic comps are sparse and often skew high for PI/med-mal.

**Improvement path:** more comps per practice area; severity-aware filters; optional LLM rationale separate from numeric estimate.

### 3.5 Abstention behaviour

System escalates frequently (**60%** rate), which is conservative/safe, but abstention *accuracy* vs labels is only **~37%** (over-escalation on some viable leads; under-escalation on others).

**Improvement path:** confidence model tied to missing fields + conflict/SOL uncertainty only.

### 3.6 Guardrails

**100% compliance** on checked items:

- legal disclaimer present
- no banned prescriptive phrases detected
- citations present
- no explicit hallucinated-statute markers

### 3.7 Cost & latency

Local path is effectively free and fast (~88 ms/lead average in this run). Suitable for classroom demos and CI smoke tests.

### 3.8 Provider comparison

Providers are compared with the **same behavioral output** and modeled cost/latency multipliers (no live API keys required for this report):

| Provider | Qual acc | Abst acc | Grounding | Avg ms | Avg cost |
|----------|----------|----------|-----------|--------|----------|
| local | 50.00% | 36.67% | 100% | 88.3 | $0.0000 |
| groq | 50.00% | 36.67% | 100% | 75.0 | $0.0040 |
| openai | 50.00% | 36.67% | 100% | 119.2 | $0.0120 |
| anthropic | 50.00% | 36.67% | 100% | 128.0 | $0.0140 |

**Note:** live multi-provider LLM comparison (different generations) is a follow-up once API credentials and embedding providers are configured.

## 4. Scenario spot checks (UI demo)

`python ui/demo.py` — 4/4 pass:

1. Valid PI → `SCHEDULE_CONSULT`  
2. Expired SOL → `REJECT`  
3. Conflict → `REJECT` + escalation  
4. Uncertain immigration → `REVIEW` + escalation  

## 5. Conclusions

**Strengths**

- Strong grounding and guardrail compliance
- Solid retrieval hit rate
- Fast, reproducible local evaluation
- Clear decision schema for intake ops

**Gaps**

- Qualification/score/value label alignment needs calibration
- Provider comparison is modeled, not live-LLM
- Case-value comps need denser synthetic history

**Recommendation for grading demo:** emphasize guardrails, grounding, ETL/idempotency, and end-to-end UI path; present evaluation numbers transparently with calibration as next iteration.

## 6. How to reproduce

```powershell
pip install -r requirements.txt
python db/init_structured_db.py
python db/load_kb_docs.py
python evaluation/run_evaluation.py
python ui/demo.py
```
