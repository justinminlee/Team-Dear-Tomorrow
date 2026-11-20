from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class DimFutureSelf(Base):
    __tablename__ = 'dim_future_self'
    __table_args__ = (
        CheckConstraint('years_ahead IN (5,10,20)', name='future_years_ahead_ck'),
        UniqueConstraint('future_self_id', 'user_id', name='uq_future_self_owner'),
        {"schema": "public"},
    )

    future_self_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    scenario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_scenario.scenario_id'), nullable=False)

    years_ahead: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    future_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    persona_name: Mapped[str] = mapped_column(Text, nullable=False)

    persona_profile: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    generation_model: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
