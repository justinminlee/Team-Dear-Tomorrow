from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class DimVoiceAsset(Base):
    __tablename__ = 'dim_voice_asset'
    __table_args__ = (
        ForeignKeyConstraint(['future_self_id', 'user_id'], ['public.dim_future_self.future_self_id', 'public.dim_future_self.user_id'], name='fk_voice_future_self', ondelete='CASCADE'),
        UniqueConstraint('voice_asset_id', 'user_id', name='uq_voice_asset_owner'),
        CheckConstraint("status IN ('pending','ready','failed','deleted')", name='voice_status_ck'),
        CheckConstraint("voice_type IN ('uploaded_sample','cloned_voice','default_tts','generated_audio')", name='voice_type_ck'),
        {"schema": "public"},
    )

    voice_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    future_self_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    voice_type: Mapped[str] = mapped_column(Text, nullable=False)

    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    provider_voice_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
