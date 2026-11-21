"""Running total of one speaking habit (e.g. "you know") for one style key."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FactSpeakingPattern(Base):
    __tablename__ = "fact_speaking_pattern"
    __table_args__ = (
        UniqueConstraint("voice_id", "category", "expression"),
        Index("idx_speaking_pattern_voice_expression", "voice_id", "expression"),
        {"schema": "public"},
    )

    # BIGINT identity on PostgreSQL; INTEGER on SQLite so it autoincrements in tests.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(always=True), primary_key=True
    )

    voice_id: Mapped[str] = mapped_column(
        Text, ForeignKey("public.dim_voice_style.voice_id", ondelete="CASCADE"), nullable=False
    )

    category: Mapped[str] = mapped_column(Text, nullable=False)

    expression: Mapped[str] = mapped_column(Text, nullable=False)

    # 'rule' (known vocabulary) or 'llm' (discovered by the LLM)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'rule'"))

    # 1 for words like "like" that are only sometimes a habit
    context_dependent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Number of distinct transcripts that contained it
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
