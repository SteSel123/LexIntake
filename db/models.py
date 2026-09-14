"""SQLAlchemy models for LexIntake structured entities.

Maps firm CRM-style tables (clients, attorneys, cases) and KB reference tables
(practice areas, SOL rules, acceptance criteria) used by Agno tools and seeding.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Server default works on PostgreSQL.
_CREATED_AT = text("CURRENT_TIMESTAMP")


class Base(DeclarativeBase):
    """Declarative base for Alembic autogenerate and ORM mappings."""

    pass


# --- CRM entities (migration 001) ------------------------------------------


class Client(Base):
    """Prospective or past client contact record."""

    __tablename__ = "clients"
    __table_args__ = (Index("idx_clients_state", "state"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)

    past_cases: Mapped[list[PastCase]] = relationship("PastCase", back_populates="client")


class Attorney(Base):
    """Firm attorney profile for routing and conflict checks."""

    __tablename__ = "attorneys"
    __table_args__ = (Index("idx_attorneys_availability", "availability"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    specialization: Mapped[str] = mapped_column(Text, nullable=False)
    experience_years: Mapped[int | None] = mapped_column(Integer)
    jurisdictions: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)

    past_cases: Mapped[list[PastCase]] = relationship("PastCase", back_populates="attorney")


class PastCase(Base):
    """Historical matter used for similarity and acceptance benchmarking."""

    __tablename__ = "past_cases"
    __table_args__ = (
        Index("idx_past_cases_practice_area", "practice_area"),
        Index("idx_past_cases_jurisdiction", "jurisdiction"),
        Index("idx_past_cases_attorney_id", "attorney_id"),
        Index("idx_past_cases_client_id", "client_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    practice_area: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    facts: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str | None] = mapped_column(Text)
    settlement_amount: Mapped[int | None] = mapped_column(Integer)
    attorney_id: Mapped[str | None] = mapped_column(Text, ForeignKey("attorneys.id"))
    client_id: Mapped[str | None] = mapped_column(Text, ForeignKey("clients.id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)

    attorney: Mapped[Attorney | None] = relationship(back_populates="past_cases")
    client: Mapped[Client | None] = relationship(back_populates="past_cases")


# --- KB reference tables (migration 003) -----------------------------------


class PracticeArea(Base):
    """Canonical practice-area name list seeded from ``kb/practice_areas.json``."""

    __tablename__ = "practice_areas"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)


class SolRule(Base):
    """Statute-of-limitations snippet keyed by practice area and jurisdiction."""

    __tablename__ = "sol_rules"
    __table_args__ = (
        Index("idx_sol_rules_practice_area", "practice_area"),
        Index("idx_sol_rules_jurisdiction", "jurisdiction"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    practice_area: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_ended: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)


class AcceptanceCriteria(Base):
    """One row per practice area; criteria payload stored as JSONB."""

    __tablename__ = "acceptance_criteria"

    practice_area: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)


class IntakeLead(Base):
    """Persisted screening result from ``/analyze`` or interview completion."""

    __tablename__ = "intake_leads"
    __table_args__ = (
        Index("idx_intake_leads_created_at", "created_at"),
        Index("idx_intake_leads_jurisdiction", "jurisdiction"),
        Index("idx_intake_leads_practice_area", "practice_area"),
        Index("idx_intake_leads_decision", "decision"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    opposing_party: Mapped[str | None] = mapped_column(Text)
    practice_area: Mapped[str | None] = mapped_column(Text)
    case_type: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(Text)
    incident_date: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    damages: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[str | None] = mapped_column(Text)
    narrative: Mapped[str | None] = mapped_column(Text)
    uncertain: Mapped[bool | None] = mapped_column(Boolean)
    lead_score: Mapped[int | None] = mapped_column(Integer)
    decision: Mapped[str | None] = mapped_column(Text)
    case_viability: Mapped[str | None] = mapped_column(Text)
    escalate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    routing_recommendation: Mapped[str | None] = mapped_column(Text)
    tool_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    citations: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)
