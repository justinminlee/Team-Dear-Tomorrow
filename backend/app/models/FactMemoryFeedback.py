from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactMemoryFeedback(Base):
    __tablename__ = 'fact_memory_feedback'
    __table_args__ = (
        ForeignKeyConstraint(['memory_id', 'user_id'], ['public.fact_ai_memory.memory_id', 'public.fact_ai_memory.user_id'], name='fk_feedback_memory_owner', ondelete='CASCADE'),
        CheckConstraint("action IN ('confirm','reject','correct','delete')", name='memory_feedback_action_ck'),
        {"schema": "public"},
    )

    feedback_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    action: Mapped[str] = mapped_column(Text, nullable=False)

    corrected_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
