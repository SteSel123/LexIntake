"""LexIntake FastAPI entrypoint.

Run:
    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import health, intake, interview

app = FastAPI(
    title="LexIntake API",
    description=(
        "Backend HTTP API for law-firm lead intake screening. "
        "This is not legal advice. Consult a licensed attorney."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(intake.router)
app.include_router(interview.router)
