from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class DimUserProfile(Base):
    __tablename__ = 'dim_user_profile'
    __table_args__ = (
        {"schema": "public"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), primary_key=True)

    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    occupation: Mapped[str | None] = mapped_column(Text, nullable=True)

    goals: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    values_profile: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    lifestyle: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
