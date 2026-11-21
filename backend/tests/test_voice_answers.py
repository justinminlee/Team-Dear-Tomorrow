"""Spoken questionnaire answers: transcription and style samples (no real network or DB)."""
import asyncio
import uuid

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import voice_answers as va
from app.api.auth import current_user
from app.database.session import get_db
from app.main import app

USER = {"id": str(uuid.uuid4()), "email": "t@example.com", "username": "Tester"}
Q1, Q2, Q3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_word_count_matches_the_voice_app():
    assert va.word_count("um I don't know, bro") == 5
    assert va.word_count("") == 0


def test_sample_id_is_stable_and_specific():
    a = va.sample_id("u1", Q1, "um bro")
    assert a == va.sample_id("u1", Q1, "um bro")
    assert a != va.sample_id("u1", Q1, "um bro yeah")
    assert a != va.sample_id("u2", Q1, "um bro")
    assert len(a) == 32


# ---------- AssemblyAI calls ----------

def assemblyai(statuses, text="um so like i wanna build stuff"):
    """Fake AssemblyAI: upload, create, then the given statuses when polled."""
    calls = []
    polls = iter(statuses)

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v2/upload":
            return httpx.Response(200, json={"upload_url": "https://cdn/x"})
        if request.method == "POST" and request.url.path == "/v2/transcript":
            body = request.read().decode()
            assert '"disfluencies":true' in body.replace(" ", "")
            assert '"filter_profanity":false' in body.replace(" ", "")
            return httpx.Response(200, json={"id": "t1"})
        if request.method == "GET":
            status = next(polls)
            return httpx.Response(200, json={"status": status, "text": text if status == "completed" else None,
                                             "error": "bad audio" if status == "error" else None})
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    monkeypatch.setattr(va, "POLL_SECONDS", 0)


def test_transcribe_waits_for_completion_and_deletes_the_copy():
    client, calls = assemblyai(["queued", "processing", "completed"], text="  um  so like   i wanna build stuff ")
    assert asyncio.run(va.transcribe_audio(b"audio", client)) == "um so like i wanna build stuff"
    assert ("DELETE", "/v2/transcript/t1") in calls


def test_transcription_error_is_a_clear_422_and_still_deletes():
    client, calls = assemblyai(["error"])
    with pytest.raises(HTTPException) as err:
        asyncio.run(va.transcribe_audio(b"audio", client))
    assert err.value.status_code == 422
    assert ("DELETE", "/v2/transcript/t1") in calls


def test_service_down_is_a_502():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(HTTPException) as err:
        asyncio.run(va.transcribe_audio(b"audio", client))
    assert err.value.status_code == 502


def test_missing_key_is_a_503(monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_API_KEY")
    with pytest.raises(HTTPException) as err:
        va.assemblyai_key()
    assert err.value.status_code == 503


# ---------- endpoints ----------

@pytest.fixture
def client(monkeypatch):
    stored = []
    latest = {Q1: "um so like i wanna build stuff", Q2: "honestly bro i dunno", Q3: 7}

    def fake_store(db, user, samples):
        stored.extend(samples)
        return len(samples)

    async def fake_transcribe(audio):
        return "um yeah"

    monkeypatch.setattr(va, "load_latest_answers", lambda db, uid: dict(latest))
    monkeypatch.setattr(va, "store_samples", fake_store)
    monkeypatch.setattr(va, "transcribe_audio", fake_transcribe)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[current_user] = lambda: USER
    yield TestClient(app), stored
    app.dependency_overrides.clear()


def test_transcribe_endpoint(client):
    c, stored = client
    r = c.post("/questionnaire/transcribe", files={"audio": ("a.webm", b"x" * 2000, "audio/webm;codecs=opus")})
    assert r.status_code == 200 and r.json() == {"text": "um yeah"}
    assert stored == []  # nothing is saved until the answers are saved


@pytest.mark.parametrize("name, data, kind, status", [
    ("a.txt", b"x" * 2000, "text/plain", 415),
    ("a.webm", b"x" * 10, "audio/webm", 422),
])
def test_transcribe_rejects_bad_uploads(client, name, data, kind, status):
    c, _ = client
    assert c.post("/questionnaire/transcribe", files={"audio": (name, data, kind)}).status_code == status


def test_transcribe_requires_login():
    assert TestClient(app).post("/questionnaire/transcribe",
                                files={"audio": ("a.webm", b"x" * 2000, "audio/webm")}).status_code == 401


def test_voice_samples_use_only_saved_text_answers(client):
    c, stored = client
    unknown = uuid.uuid4()
    r = c.post("/questionnaire/voice-samples",
               json={"question_ids": [str(Q1), str(Q1), str(Q2), str(Q3), str(unknown)]})
    assert r.status_code == 200 and r.json() == {"queued": 2}
    # Duplicates, non-text answers (Q3 is a number) and unsaved questions are ignored.
    assert stored == [(Q1, "um so like i wanna build stuff"), (Q2, "honestly bro i dunno")]


def test_voice_samples_with_nothing_usable(client):
    c, stored = client
    assert c.post("/questionnaire/voice-samples", json={"question_ids": [str(Q3)]}).json() == {"queued": 0}
    assert stored == []
    assert c.post("/questionnaire/voice-samples", json={"question_ids": []}).status_code == 422
