"""What the user said in one recording, queued for speaking style analysis."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy import text as sql_text  # "text" is also a column name below
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FactTranscript(Base):
    __tablename__ = "fact_transcript"
    __table_args__ = (
        Index("idx_fact_transcript_status", "voice_id", "analysis_status", "llm_analysis_status"),
        {"schema": "public"},
    )

    transcript_id: Mapped[str] = mapped_column(Text, primary_key=True)

    voice_id: Mapped[str] = mapped_column(
        Text, ForeignKey("public.dim_voice_style.voice_id", ondelete="CASCADE"), nullable=False
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)

    word_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # pending -> processing -> completed (or failed, retried up to a limit)
    analysis_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'pending'"))

    llm_analysis_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'pending'"))

    rule_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))

    llm_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    llm_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
