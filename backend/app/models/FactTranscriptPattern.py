import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FactTranscriptPattern(Base):
    """How often one expression appeared in one transcript.

    The (transcript_id, expression) primary key is what prevents double counting:
    if both the rules and the LLM find "um" in the same turn, or a failed analysis is
    retried, the turn still only adds to fact_speaking_pattern once.
    """

    __tablename__ = "fact_transcript_pattern"
    __table_args__ = {"schema": "public"}

    # Primary Key + Foreign Key
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.dim_transcript.transcript_id", ondelete="CASCADE"),
        primary_key=True
    )

    # Primary Key
    expression: Mapped[str] = mapped_column(
        String(40),
        primary_key=True
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
