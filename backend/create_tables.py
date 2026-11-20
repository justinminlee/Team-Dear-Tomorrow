"""Create the 15 Me² AI tables using individual SQLAlchemy ORM models.

From backend/:
    python create_tables.py --check
    python create_tables.py

Never drops tables or deletes data. Existing table definitions are NOT migrated.
Supabase Auth users are referenced but never created.
"""
import argparse
import sys
from sqlalchemy import inspect, text, Index
from sqlalchemy.exc import SQLAlchemyError
from app.database.base import Base
from app.database.session import engine
import app.models  # noqa: F401: registers every model
from seed_data import seed_data

TABLES = [t for t in Base.metadata.sorted_tables if t.schema == "public"]

INDEXES = [
    ("idx_future_self_user", "dim_future_self", ["user_id"]),
    ("idx_question_questionnaire", "dim_question", ["questionnaire_id", "display_order"]),
    ("idx_answer_user_question", "fact_profile_answer", ["user_id", "question_id", "answered_at"]),
    ("idx_answer_future", "fact_profile_answer", ["future_self_id", "answered_at"]),
    ("idx_conversation_user_started", "fact_conversation", ["user_id", "started_at"]),
    ("idx_conversation_future", "fact_conversation", ["future_self_id", "started_at"]),
    ("idx_message_conversation_time", "fact_message", ["conversation_id", "created_at", "message_id"]),
    ("idx_message_user_time", "fact_message", ["user_id", "created_at"]),
    ("idx_consent_user_type_time", "fact_consent", ["user_id", "consent_type", "recorded_at"]),
    ("idx_voice_user", "dim_voice_asset", ["user_id"]),
    ("idx_debate_user", "fact_agent_debate", ["user_id"]),
    ("idx_share_user", "fact_share", ["user_id"]),
    ("idx_persona_version_future", "fact_persona_version", ["future_self_id", "version_number"]),
    ("idx_memory_future_status", "fact_ai_memory", ["future_self_id", "status", "created_at"]),
    ("idx_memory_feedback_memory", "fact_memory_feedback", ["memory_id", "created_at"]),
]


def check_tables(conn):
    inspector = inspect(conn)
    missing = []
    missing_cols = []
    for t in TABLES:
        if not inspector.has_table(t.name, schema="public"):
            missing.append(t.name)
            continue
        present = {c["name"] for c in inspector.get_columns(t.name, schema="public")}
        missing_cols.extend(f"{t.name}.{c.name}" for c in t.columns if c.name not in present)
    print(f"Present: {len(TABLES)-len(missing)}/{len(TABLES)} tables")
    if missing: print("Missing tables:", ", ".join(missing))
    if missing_cols: print("Missing columns:", ", ".join(missing_cols))
    return missing, missing_cols


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Inspect only; never modify database")
    args = parser.parse_args()
    try:
        if args.check:
            with engine.connect() as conn:
                print("Connected as:", conn.execute(text("SELECT current_user")).scalar())
                check_tables(conn)
            return
        with engine.begin() as conn:
            role = conn.execute(text("SELECT current_user")).scalar()
            print("Connected as:", role)
            can_create = conn.execute(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")).scalar()
            if not can_create:
                raise RuntimeError(f"{role} cannot CREATE in public. Use a migration/admin connection.")
            # create_all sorts foreign key references in correct order.
            Base.metadata.create_all(bind=conn, tables=TABLES, checkfirst=True)
            # CREATE IF NOT EXISTS protects repeated execution.
            for name, tbl, cols in INDEXES:
                Index(name, *(Base.metadata.tables[f"public.{tbl}"].c[c] for c in cols)).create(bind=conn, checkfirst=True)
            missing, missing_cols = check_tables(conn)
            if missing or missing_cols:
                raise RuntimeError("Existing tables differ from these models; use Alembic migrations.")
            seed_data(conn)
        print("Finished creating/checking 15 tables and seeding 20 questions.")
        print("RLS, grants, and schema migrations must be managed separately.")
    except (SQLAlchemyError, RuntimeError) as exc:
        print("Database setup failed:", exc, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
