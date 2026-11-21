"""Shared test setup.

Every test gets an in-memory SQLite copy of the speaking-style tables in place of
Supabase, so no test can read or write the real database through the style store.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import DimVoiceStyle, FactSpeakingPattern, FactTranscript, FactTranscriptPattern
from app.services import style_service
from app.services.style_store import StyleStore


def memory_style_store() -> StyleStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    ).execution_options(schema_translate_map={"public": None})
    tables = [m.__table__ for m in (DimVoiceStyle, FactTranscript, FactSpeakingPattern, FactTranscriptPattern)]
    DimVoiceStyle.metadata.create_all(engine, tables=tables)
    return StyleStore(engine)


@pytest.fixture
def style_store() -> StyleStore:
    return memory_style_store()


@pytest.fixture(autouse=True)
def _no_real_style_db(style_store, monkeypatch):
    # Endpoints get the store through this dependency. Some test files clear
    # app.dependency_overrides when they finish, so set it again for every test.
    app.dependency_overrides[style_service.get_style_store] = lambda: style_store
    # And never call the real LLM for style analysis unless a test says so.
    monkeypatch.setattr(style_service, "analysis_chat", lambda *a, **k: '{"habits": [], "tone": {}, "notes": []}')
    yield
    app.dependency_overrides.pop(style_service.get_style_store, None)
