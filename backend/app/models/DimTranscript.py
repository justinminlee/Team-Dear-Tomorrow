import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base

STATUSES = "('pending', 'processing', 'completed', 'failed')"


class DimTranscript(Base):
    """One thing the user said (their own speech only, never the AI's reply), queued for style analysis.

    The text lives here instead of in a .txt file, because a server can't rely on local files.
    """

    __tablename__ = "dim_transcript"
    __table_args__ = (
        CheckConstraint(f"analysis_status IN {STATUSES}", name="ck_transcript_analysis_status"),
        CheckConstraint(f"llm_analysis_status IN {STATUSES}", name="ck_transcript_llm_analysis_status"),
        Index("ix_transcript_voice_status", "voice_id", "analysis_status", "llm_analysis_status"),
        {"schema": "public"},
    )

    # Primary Key
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign Key
    voice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.dim_voice_style.voice_id", ondelete="CASCADE"),
        nullable=False
    )

    # Foreign Key (optional): the chat message this transcript came from
    msg_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("public.dim_msg.msg_id", ondelete="SET NULL"),
        nullable=True
    )

    # What the user said
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Rule-based analysis (runs every turn)
    analysis_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending"
    )

    # LLM-based contextual analysis
    llm_analysis_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending"
    )

    # Retry counters, so a broken transcript is eventually skipped
    rule_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0"
    )

    llm_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    llm_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
