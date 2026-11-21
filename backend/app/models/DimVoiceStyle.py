"""Learned speaking style, one row per style key.

The table already exists in Supabase. `voice_id` is a free-text key: the web app
uses "user-<auth user id>" so every user gets their own profile.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

# JSONB on PostgreSQL, plain JSON elsewhere (the tests run on SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class DimVoiceStyle(Base):
    __tablename__ = "dim_voice_style"
    __table_args__ = ({"schema": "public"},)

    voice_id: Mapped[str] = mapped_column(Text, primary_key=True)

    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_words: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Accumulated tone votes, e.g. {"formality": {"informal": 3}}
    tone_profile: Mapped[Any] = mapped_column(JSONType, nullable=False, server_default=text("'{}'"))

    # Latest contextual notes from the LLM, e.g. {"notes": [...]}
    speaking_habits: Mapped[Any] = mapped_column(JSONType, nullable=False, server_default=text("'{}'"))

    # NULL = not asked yet, 0 = no, 1 = yes
    learning_enabled: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
