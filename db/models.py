"""SQLAlchemy models for LexIntake structured entities."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Server default works on PostgreSQL.
_CREATED_AT = text("CURRENT_TIMESTAMP")


class Base(DeclarativeBase):
    pass


class Client(Base):
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


class PracticeArea(Base):
    __tablename__ = "practice_areas"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)


class SolRule(Base):
    __tablename__ = "sol_rules"
    __table_args__ = (
        Index("idx_sol_rules_practice_area", "practice_area"),
        Index("idx_sol_rules_jurisdiction", "jurisdiction"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    practice_area: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)


class AcceptanceCriteria(Base):
    """One row per practice area; criteria payload stored as JSONB."""

    __tablename__ = "acceptance_criteria"

    practice_area: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_CREATED_AT)
