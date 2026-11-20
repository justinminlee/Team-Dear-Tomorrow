from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FactProfileAnswer(Base):
    __tablename__ = 'fact_profile_answer'
    __table_args__ = (
        ForeignKeyConstraint(['future_self_id', 'user_id'], ['public.dim_future_self.future_self_id', 'public.dim_future_self.user_id'], name='fk_answer_future_owner', ondelete='CASCADE'),
        {"schema": "public"},
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_user_profile.user_id', ondelete='CASCADE'), nullable=False)

    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_question.question_id'), nullable=False)

    future_self_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    answer_value: Mapped[Any] = mapped_column(JSONB, nullable=False)

    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
