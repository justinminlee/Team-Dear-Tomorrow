from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactConsent(Base):
    __tablename__ = 'fact_consent'
    __table_args__ = (
        CheckConstraint('NOT granted OR granted_at IS NOT NULL', name='consent_granted_at_ck'),
        CheckConstraint("consent_type IN ('voice_cloning','voice_storage','share_content','privacy_terms')", name='consent_type_ck'),
        {"schema": "public"},
    )

    consent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    consent_type: Mapped[str] = mapped_column(Text, nullable=False)

    consent_version: Mapped[str] = mapped_column(Text, nullable=False)

    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)

    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
