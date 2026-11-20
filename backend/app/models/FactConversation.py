from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactConversation(Base):
    __tablename__ = 'fact_conversation'
    __table_args__ = (
        CheckConstraint("conversation_type IN ('single','debate')", name='conversation_type_ck'),
        ForeignKeyConstraint(['future_self_id', 'user_id'], ['public.dim_future_self.future_self_id', 'public.dim_future_self.user_id'], name='fk_conversation_future_owner'),
        UniqueConstraint('conversation_id', 'user_id', name='uq_conversation_owner'),
        {"schema": "public"},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    future_self_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    conversation_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'single'"))

    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
