"""Metadata-only reference to Supabase Auth. Never create this table."""
from sqlalchemy import Table, Column
from sqlalchemy.dialects.postgresql import UUID
from app.database.base import Base

auth_users = Table(
    "users", Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
