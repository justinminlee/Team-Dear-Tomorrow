"""Which habits one transcript contributed. Makes re-analysis safe from double counting."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FactTranscriptPattern(Base):
    __tablename__ = "fact_transcript_pattern"
    __table_args__ = ({"schema": "public"},)

    transcript_id: Mapped[str] = mapped_column(
        Text, ForeignKey("public.fact_transcript.transcript_id", ondelete="CASCADE"), primary_key=True
    )

    expression: Mapped[str] = mapped_column(Text, primary_key=True)

    category: Mapped[str] = mapped_column(Text, nullable=False)

    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
