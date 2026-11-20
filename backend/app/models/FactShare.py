from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactShare(Base):
    __tablename__ = 'fact_share'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id', 'user_id'], ['public.fact_conversation.conversation_id', 'public.fact_conversation.user_id'], name='fk_share_conv', ondelete='CASCADE'),
        CheckConstraint("platform IN ('instagram','tiktok','other')", name='share_platform_ck'),
        CheckConstraint("share_status IN ('draft','published','revoked')", name='share_status_ck'),
        {"schema": "public"},
    )

    share_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    platform: Mapped[str | None] = mapped_column(Text, nullable=True)

    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    share_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
