from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactMessage(Base):
    __tablename__ = 'fact_message'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id', 'user_id'], ['public.fact_conversation.conversation_id', 'public.fact_conversation.user_id'], name='fk_msg_conversation', ondelete='CASCADE'),
        ForeignKeyConstraint(['future_self_id', 'user_id'], ['public.dim_future_self.future_self_id', 'public.dim_future_self.user_id'], name='fk_msg_future_self'),
        ForeignKeyConstraint(['audio_asset_id', 'user_id'], ['public.dim_voice_asset.voice_asset_id', 'public.dim_voice_asset.user_id'], name='fk_msg_voice'),
        CheckConstraint("input_mode IN ('text','voice')", name='message_input_mode_ck'),
        CheckConstraint("role IN ('user','assistant','system')", name='message_role_ck'),
        CheckConstraint('token_count IS NULL OR token_count >= 0', name='message_tokens_ck'),
        CheckConstraint("role <> 'assistant' OR future_self_id IS NOT NULL", name='msg_persona_for_assistant'),
        {"schema": "public"},
    )

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    future_self_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    scenario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_scenario.scenario_id'), nullable=True)

    role: Mapped[str] = mapped_column(Text, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    input_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'text'"))

    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
