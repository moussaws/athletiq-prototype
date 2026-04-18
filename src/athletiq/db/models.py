"""ORM models for persisted AHP preferences and saved squads.

Schema is intentionally small: both resources are self-contained snapshots
(criteria + weights + matrix for prefs; assignments + totals for squads) so
the UI can re-hydrate a session without re-running the optimizer.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    pass


class AhpPreference(Base):
    """A named AHP pairwise matrix + derived weights and consistency ratio."""

    __tablename__ = "ahp_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    pairwise_matrix: Mapped[list[list[float]]] = mapped_column(JSON, nullable=False)
    weights: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    consistency_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    is_consistent: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class SavedSquad(Base):
    """A solved XI: references the preference used + serialised assignments."""

    __tablename__ = "saved_squads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    preference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weights: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    formation: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    budget: Mapped[float] = mapped_column(Float, nullable=False)
    foreign_max: Mapped[int] = mapped_column(Integer, nullable=False)
    assignments: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    squad_gap_position: Mapped[str | None] = mapped_column(String(16), nullable=True)
    squad_gap_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    budget_used: Mapped[float] = mapped_column(Float, nullable=False)
    foreign_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
