"""LexIntake FastAPI entrypoint.

Wires CORS, registers route modules, and exposes the ASGI `app` consumed by
uvicorn. Run locally with:

    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import health, intake, interview

# --- Application factory ---------------------------------------------------
# Single FastAPI instance; OpenAPI metadata includes the legal disclaimer
# because screening output is informational, not legal advice.
app = FastAPI(
    title="LexIntake API",
    description=(
        "Backend HTTP API for law-firm lead intake screening. "
        "This is not legal advice. Consult a licensed attorney."
    ),
    version="1.0.0",
)

# CORS: default * for demos; set ALLOWED_ORIGINS to a comma-separated list in prod.
_raw_origins = (os.getenv("ALLOWED_ORIGINS") or "*").strip()
_allow_origins = (
    ["*"]
    if _raw_origins == "*"
    else [o.strip() for o in _raw_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Route registration ----------------------------------------------------
app.include_router(health.router)
app.include_router(intake.router)
app.include_router(interview.router)
