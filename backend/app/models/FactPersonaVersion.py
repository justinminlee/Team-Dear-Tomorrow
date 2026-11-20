from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactPersonaVersion(Base):
    __tablename__ = 'fact_persona_version'
    __table_args__ = (
        ForeignKeyConstraint(['future_self_id', 'user_id'], ['public.dim_future_self.future_self_id', 'public.dim_future_self.user_id'], name='fk_persona_future_owner', ondelete='CASCADE'),
        CheckConstraint('version_number > 0', name='persona_version_positive_ck'),
        UniqueConstraint('future_self_id', 'version_number', name='uq_persona_version'),
        {"schema": "public"},
    )

    persona_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    future_self_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    persona_snapshot: Mapped[Any] = mapped_column(JSONB, nullable=False)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    generation_model: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
