"""Shared test setup. External APIs are never called: tests use fake keys and fake LLM replies."""
import os
import sys
from pathlib import Path

# Fake settings must be in place before config.py loads .env (load_dotenv never overrides them).
os.environ.setdefault("ASSEMBLYAI_API_KEY", "test-key")
os.environ.setdefault("TJ_VOICE_ID", "voice_tj")
os.environ.setdefault("PETER_VOICE_ID", "voice_peter")
os.environ.setdefault("LUCAS_VOICE_ID", "voice_lucas")
os.environ["ASSEMBLYAI_API_KEY"] = "test-key"
os.environ["STYLE_DB"] = "sqlite"  # tests never touch Supabase

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from database import StyleDatabase, set_database  # noqa: E402
from style_analyzer import word_count  # noqa: E402
from transcript import save_transcript  # noqa: E402


# Set VOICE_TEST_PG_URL to a throwaway local PostgreSQL to run the same tests on the
# Supabase backend code. Each test gets its own schema, dropped afterwards.
PG_URL = os.getenv("VOICE_TEST_PG_URL")


@pytest.fixture
def db(tmp_path):
    if PG_URL:
        import uuid

        import psycopg

        from database import PostgresStyleDatabase

        schema = "test_" + uuid.uuid4().hex[:12]
        database = PostgresStyleDatabase(PG_URL, schema=schema, max_size=4)
    else:
        database = StyleDatabase(tmp_path / "test.db")
    set_database(database)
    yield database
    set_database(None)
    database.close()
    if PG_URL:
        with psycopg.connect(PG_URL, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture
def tdir(tmp_path):
    return tmp_path / "transcripts"


@pytest.fixture
def add_transcript(db, tdir):
    """Save and register a transcript the same way the app does. Returns its id."""
    def _add(text, voice_id="voice_a"):
        transcript_id, _ = save_transcript(text, voice_id, tdir)
        db.register_transcript(transcript_id, voice_id, text, word_count(text))
        return transcript_id
    return _add


class FakeChat:
    """Stands in for llm.chat: returns queued replies (or raises queued exceptions)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, messages, max_tokens=200, temperature=None):
        self.calls.append(messages)
        reply = self.replies.pop(0) if self.replies else '{"habits": []}'
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def fake_chat():
    return FakeChat
