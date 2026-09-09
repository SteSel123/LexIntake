# LexIntake — common developer tasks
# Requires: Docker Compose (+ GNU Make). Windows: `choco install make` or Git Bash / WSL
# Local Python targets also need Python 3.11+

.PHONY: help install env setup down logs ps db-up db-down db-reset \
	init-db etl setup-local ui api demo eval test dashboard clean \
	docker-build docker-up docker-down docker-logs docker-ps

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
COMPOSE ?= docker compose
PYTHONPATH ?= .
export PYTHONPATH
STREAMLIT ?= $(PYTHON) -m streamlit
UVICORN ?= $(PYTHON) -m uvicorn

.DEFAULT_GOAL := help

help:
	@$(PYTHON) -c "print('''LexIntake Make targets\n\nDefault (full Docker stack):\n  make setup       Create .env if needed, build and start everything\n  make down        Stop all Compose services\n  make logs        Follow Compose logs\n  make ps          Show Compose status\n\n  UI  http://localhost:8501\n  API http://localhost:8000/docs\n\nOptional — local Python (Postgres container only):\n  make setup-local pip + Postgres + schema + ETL on the host\n  make db-up       Start Postgres only\n  make ui / api    Run Streamlit / FastAPI on the host\n  make demo / eval Host-side demo and evaluation\n\nSet OPENAI_API_KEY in .env before starting.''')"

env:
	@$(PYTHON) scripts/ensure_env.py

# --- Default: full stack in Docker ---

setup: env
	$(COMPOSE) up --build -d
	@$(PYTHON) -c "print('\\nStack up.\\n  UI:  http://localhost:8501\\n  API: http://localhost:8000/docs\\nEnsure OPENAI_API_KEY is set in .env')"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

docker-build: env
	$(COMPOSE) build

docker-up: setup

docker-down: down

docker-logs: logs

docker-ps: ps

# --- Optional: host Python + Postgres only ---

install:
	$(PIP) install -r requirements.txt

db-up:
	$(COMPOSE) up -d --wait postgres

db-down: down

db-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d --wait postgres

init-db:
	$(PYTHON) -m db.init_structured_db

etl:
	$(PYTHON) -m etl.pipeline

setup-local: install env db-up init-db etl
	@$(PYTHON) -c "print('\\nLocal setup complete.\\n1. Edit .env and set OPENAI_API_KEY\\n2. make ui\\n3. make api   (optional)')"

ui:
	$(STREAMLIT) run frontend/app.py

api:
	$(UVICORN) backend.api.main:app --reload --port 8000

demo:
	$(PYTHON) frontend/demo.py

eval:
	$(PYTHON) evaluation/run_evaluation.py --providers openai:gpt-4.1 --limit 5 --require-all

test:
	$(PYTHON) -m pytest tests/ -q

dashboard:
	$(PYTHON) -m streamlit run monitoring/dashboard.py

clean:
	@$(PYTHON) scripts/clean_pycache.py
