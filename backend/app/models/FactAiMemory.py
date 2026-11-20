from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactAiMemory(Base):
    __tablename__ = 'fact_ai_memory'
    __table_args__ = (
        ForeignKeyConstraint(['future_self_id', 'user_id'], ['public.dim_future_self.future_self_id', 'public.dim_future_self.user_id'], name='fk_memory_future_owner', ondelete='CASCADE'),
        CheckConstraint('confidence IS NULL OR confidence BETWEEN 0 AND 100', name='memory_confidence_ck'),
        CheckConstraint("status IN ('proposed','confirmed','rejected','deleted')", name='memory_status_ck'),
        CheckConstraint("memory_type IN ('goal','preference','value','fact','concern','milestone','other')", name='memory_type_ck'),
        UniqueConstraint('memory_id', 'user_id', name='uq_memory_owner'),
        {"schema": "public"},
    )

    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    future_self_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    source_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('public.fact_message.message_id', ondelete='SET NULL'), nullable=True)

    memory_type: Mapped[str] = mapped_column(Text, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'proposed'"))

    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
