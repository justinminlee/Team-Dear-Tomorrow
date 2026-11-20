import uuid

from sqlalchemy import Integer, TEXT, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.base import Base


class DimVoice(Base):
    __tablename__ = "dim_voice"
    __table_args__ = {"schema": "public"}

    # Foreign Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.fact_user.id", ondelete="CASCADE"),
        nullable=False
    )

    # Foreign Key
    chat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.dim_chat.chat_id", ondelete="CASCADE"),
        nullable=False
    )

    # Primary Key
    voice_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # voice
    voice: Mapped[str] = mapped_column(
        TEXT,
        nullable=False
    )
