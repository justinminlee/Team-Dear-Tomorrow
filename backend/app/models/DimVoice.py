import uuid
from datetime import datetime

from sqlalchemy import TEXT, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.base import Base


class DimVoice(Base):
    """A cloned voice owned by a user.

    A voice belongs to the user, not to a single chat, so the same voice can be used
    across many chats and its speaking style (dim_voice_style) keeps building up.
    Which voice a chat uses is stored on dim_chat.voice_id.
    """

    __tablename__ = "dim_voice"
    __table_args__ = (
        # The same AssemblyAI voice is registered only once per user
        UniqueConstraint("id", "voice", name="uq_voice_user_voice"),
        {"schema": "public"},
    )

    # Foreign Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.fact_user.id", ondelete="CASCADE"),
        nullable=False
    )

    # Primary Key
    voice_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # voice (AssemblyAI Voice ID)
    voice: Mapped[str] = mapped_column(
        TEXT,
        nullable=False
    )

    # Created Date
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
