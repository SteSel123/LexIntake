"""SQLAlchemy models for LexIntake structured entities."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("(datetime('now'))")
    )

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
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("(datetime('now'))")
    )

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
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("(datetime('now'))")
    )

    attorney: Mapped[Attorney | None] = relationship(back_populates="past_cases")
    client: Mapped[Client | None] = relationship(back_populates="past_cases")
