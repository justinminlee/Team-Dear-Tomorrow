import uuid
from datetime import datetime

from sqlalchemy import Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.base import Base


class DimChat(Base):
    __tablename__ = "dim_chat"
    __table_args__ = {"schema": "public"}

    # Foreign Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.fact_user.id", ondelete="CASCADE"),
        nullable=False
    )

    # Primary Key
    chat_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # Created Date
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Simulation Period
    yearahead: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )