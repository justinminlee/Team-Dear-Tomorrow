from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactAgentDebate(Base):
    __tablename__ = 'fact_agent_debate'
    __table_args__ = (
        CheckConstraint("status IN ('created','running','completed','failed')", name='debate_status_ck'),
        ForeignKeyConstraint(['conversation_id', 'user_id'], ['public.fact_conversation.conversation_id', 'public.fact_conversation.user_id'], name='fk_debate_conv', ondelete='CASCADE'),
        UniqueConstraint('conversation_id', name='uq_debate_conv'),
        {"schema": "public"},
    )

    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    topic: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'created'"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
