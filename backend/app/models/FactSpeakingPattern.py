from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class FactSpeakingPattern(Base):
    """Running count of one speaking habit (e.g. "um", "bro") for one voice."""

    __tablename__ = "fact_speaking_pattern"
    __table_args__ = (
        UniqueConstraint("voice_id", "category", "expression", name="uq_speaking_pattern_voice_category_expression"),
        CheckConstraint("source IN ('rule', 'llm')", name="ck_speaking_pattern_source"),
        CheckConstraint("occurrence_count >= 0 AND sample_count >= 0", name="ck_speaking_pattern_counts"),
        Index("ix_speaking_pattern_voice_expression", "voice_id", "expression"),
        {"schema": "public"},
    )

    # Primary Key
    pattern_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # Foreign Key
    voice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.dim_voice_style.voice_id", ondelete="CASCADE"),
        nullable=False
    )

    # filler_words, slang, profanity, common_expressions, hesitation, repetition, informal_vocabulary
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    # Lowercase expression, 1-4 words, e.g. "you know"
    expression: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )

    # 'rule' = counted by the regex rules, 'llm' = discovered by the LLM
    source: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="rule"
    )

    # True for words like "like" that are only sometimes a habit
    context_dependent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false"
    )

    # Total times said
    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0"
    )

    # Number of distinct turns it appeared in
    sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0"
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
