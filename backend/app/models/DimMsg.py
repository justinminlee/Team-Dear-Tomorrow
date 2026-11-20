import uuid

from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.base import Base


class DimMsg(Base):
    __tablename__ = "dim_msg"
    __table_args__ = {"schema": "public"}

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

    # Message
    msg: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )