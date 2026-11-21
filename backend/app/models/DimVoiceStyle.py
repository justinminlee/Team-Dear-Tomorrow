from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class DimVoiceStyle(Base):
    """Speaking style profile for one cloned voice (one row per dim_voice row).

    Ownership comes from dim_voice.id (the user), so a user can only read the
    style of voices they own.
    """

    __tablename__ = "dim_voice_style"
    __table_args__ = {"schema": "public"}

    # Primary Key + Foreign Key (1:1 with dim_voice)
    voice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.dim_voice.voice_id", ondelete="CASCADE"),
        primary_key=True
    )

    # Running totals of everything the user has said with this voice
    total_words: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0"
    )

    total_samples: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0"
    )

    # Accumulated tone votes, e.g. {"formality": {"informal": 3}, "descriptors": {"casual": 2}}
    tone_profile: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}"
    )

    # Latest contextual notes from the LLM, e.g. {"notes": ["Says 'like' when excited"]}
    speaking_habits: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}"
    )

    # User consent: NULL = not asked yet, true = learning on, false = learning off
    learning_enabled: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
