from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, SmallInteger, Text, UniqueConstraint, text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class DimQuestion(Base):
    __tablename__ = 'dim_question'
    __table_args__ = (
        UniqueConstraint('question_code', name=None),
        CheckConstraint("response_type IN ('text','number','single_choice','multiple_choice','scale','boolean')", name='question_response_type_ck'),
        {"schema": "public"},
    )

    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))

    questionnaire_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('public.dim_questionnaire.questionnaire_id'), nullable=True)

    question_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    category: Mapped[str] = mapped_column(Text, nullable=False)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    response_type: Mapped[str] = mapped_column(Text, nullable=False)

    options: Mapped[Any | None] = mapped_column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))

    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
