import uuid

from sqlalchemy import Integer, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.base import Base


class DimQs(Base):
    __tablename__ = "dim_qs"
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
    qs_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # questions
    questions: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False
    )

    # answers
    answers: Mapped[list] = mapped_column(
        JSONB,
        nullable=False
    )