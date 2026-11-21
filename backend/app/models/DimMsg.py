from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class DimMsg(Base):
    __tablename__ = "dim_msg"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_msg_role"),
        Index("ix_msg_chat_created", "chat_id", "created_at"),
        {"schema": "public"},
    )

    # Primary Key
    msg_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # Foreign Key
    chat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.dim_chat.chat_id", ondelete="CASCADE"),
        nullable=False
    )

    # Who wrote it: 'user' (the person) or 'assistant' (Dear Tomorrow).
    # Speaking style learning only uses 'user' messages.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    # Message
    msg: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Sent Date
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
