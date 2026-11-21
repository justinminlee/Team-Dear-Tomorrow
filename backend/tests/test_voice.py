"""Speaking-style learning on the website: analysis, prompt text, and how it plugs into
POST /questionnaire/voice-samples and the future-self call (/call/start, /call/turn).

Runs on the in-memory style store from conftest.py and mocks every AssemblyAI call.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import call, voice_answers
from app.api.auth import current_user
from app.database.session import get_db
from app.main import app
from app.services import style_prompt, style_service, voice_ai
from app.services.style_learner import StyleLearner
from app.services.style_store import user_style_key

USER = {"id": str(uuid.uuid4()), "email": "t@example.com", "username": "Tester"}
KEY = user_style_key(USER["id"])

SAMPLE_1 = "Um, I'm gonna be honest, you know, I wanna run my own studio, um, like basically."
SAMPLE_2 = "Uh I dunno, you know, I'm gonna keep learning, I mean, um, it's kinda exciting."

WAV = (b"RIFF" + (36 + 320).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little")
       + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
       + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
       + b"data" + (320).to_bytes(4, "little") + b"\0" * 320)


def llm_reply(habits=None, tone=None, notes=None):
    """A fake LLM analysis reply in the JSON shape the analyzer asks for."""
    return json.dumps({
        "habits": habits or [],
        "tone": tone if tone is not None else {
            "formality": "informal", "humour": "occasional", "emotional_expression": "moderate",
            "sentence_structure": "run_on", "descriptors": ["casual", "warm"]},
        "notes": notes if notes is not None else ["Uses fillers when thinking"],
    })


def learn(store, key=KEY):
    return StyleLearner(store, lambda *a, **k: llm_reply()).process_voice(key)


# ---------- store + learner ----------

def test_style_key_is_the_user_id():
    # Same key as voice_answers.store_samples and the VOICE app.
    assert KEY == USER["id"]


def test_learning_counts_habits_and_never_double_counts(style_store):
    style_store.register_transcript("t1", KEY, SAMPLE_1, 15, display_name="Tester")
    style_store.register_transcript("t2", KEY, SAMPLE_2, 15)
    made_up = {"category": "slang", "expression": "innit", "counts": {"T1": 2}}  # not in the text
    learner = StyleLearner(style_store, lambda *a, **k: llm_reply(habits=[made_up]))

    assert learner.process_voice(KEY) == 2
    profile = style_store.get_style_profile(KEY)
    found = {p["expression"]: p for p in profile["patterns"]}

    assert profile["total_samples"] == 2 and profile["total_words"] == 30
    assert found["um"]["occurrence_count"] == 3 and found["um"]["sample_count"] == 2
    assert found["you know"]["sample_count"] == 2
    assert found["gonna"]["occurrence_count"] == 2
    assert "innit" not in found  # the LLM's invented habit is dropped
    assert "like" not in found  # ambiguous words are never counted by the rules
    assert profile["tone_profile"]["formality"] == {"informal": 2}

    # Running again (e.g. a retry, or the VOICE app) changes nothing.
    assert learner.process_voice(KEY) == 0
    assert style_store.get_style_profile(KEY)["patterns"] == profile["patterns"]


def test_llm_failure_keeps_rule_results_and_retries_later(style_store):
    style_store.register_transcript("t1", KEY, SAMPLE_1, 15)
    StyleLearner(style_store, lambda *a, **k: "not json").process_voice(KEY)
    assert style_store.get_style_profile(KEY)["total_samples"] == 1  # rule results saved
    assert style_store.llm_backlog(KEY)  # still waiting for the LLM

    learn(style_store)
    assert style_store.llm_backlog(KEY) == []


# ---------- prompt text ----------

def test_style_notes_after_two_samples(style_store):
    style_store.register_transcript("t1", KEY, SAMPLE_1, 15)
    style_store.register_transcript("t2", KEY, SAMPLE_2, 15)
    learn(style_store)
    notes = style_prompt.style_notes(style_store.get_style_profile(KEY))
    assert '"um"' in notes and '"you know"' in notes
    assert "Formality: informal" in notes
    assert "Observed in 2 of the user's own spoken turns (30 words)" in notes


def test_habits_seen_once_are_not_used(style_store):
    style_store.register_transcript("t1", KEY, SAMPLE_1, 15)
    learn(style_store)
    notes = style_prompt.style_notes(style_store.get_style_profile(KEY)) or ""
    assert '"um"' not in notes and '"gonna"' not in notes


def test_no_profile_no_notes():
    assert style_prompt.style_notes(None) is None


# ---------- questionnaire voice samples -> learned in the background ----------

@pytest.fixture
def client():
    app.dependency_overrides[current_user] = lambda: USER
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_voice_samples_are_learned_right_away(client, style_store, monkeypatch):
    q1, q2 = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(voice_answers, "load_latest_answers", lambda db, uid: {q1: SAMPLE_1, q2: SAMPLE_2})

    def fake_store_samples(db, user, samples):  # what store_samples writes, into the test store
        style_store.ensure_profile(str(user["id"]), user["username"], learning_enabled=True)
        for qid, text in samples:
            style_store.register_transcript(voice_answers.sample_id(str(user["id"]), qid, text),
                                            str(user["id"]), text, voice_answers.word_count(text))
        return len(samples)

    monkeypatch.setattr(voice_answers, "store_samples", fake_store_samples)
    monkeypatch.setattr(style_service, "analysis_chat", lambda *a, **k: llm_reply())

    res = client.post("/questionnaire/voice-samples", json={"question_ids": [str(q1), str(q2)]})
    assert res.status_code == 200, res.text
    assert res.json() == {"queued": 2}

    profile = style_store.get_style_profile(KEY)  # the background task already ran
    assert profile["total_samples"] == 2
    assert any(p["expression"] == "um" and p["sample_count"] == 2 for p in profile["patterns"])


# ---------- the call uses (and keeps learning) the style ----------

@pytest.fixture
def call_fakes(monkeypatch):
    prompts = []

    def fake_chat(messages, **kwargs):
        prompts.append(messages[0]["content"])
        return "Hey, you know, keep going."

    monkeypatch.setattr(call, "load_active_questions", lambda db: [])
    monkeypatch.setattr(call, "load_latest_answers", lambda db, uid: {})
    monkeypatch.setattr(voice_ai, "chat", fake_chat)
    monkeypatch.setattr(voice_ai, "synthesize", lambda text, voice=None: b"ID3fake-mp3")
    monkeypatch.setattr(voice_ai, "transcribe", lambda audio, context=None: SAMPLE_2)
    monkeypatch.setattr(style_service, "analysis_chat", lambda *a, **k: llm_reply())
    return prompts


def turn(client):
    return client.post("/call/turn", files={"audio": ("t.wav", WAV, "audio/wav")}, data={"history": "[]"})


def test_call_prompt_includes_learned_style(client, style_store, call_fakes):
    style_store.ensure_profile(KEY, "Tester", learning_enabled=True)
    style_store.register_transcript("t1", KEY, SAMPLE_1, 15)
    style_store.register_transcript("t2", KEY, SAMPLE_2, 15)
    learn(style_store)

    assert client.post("/call/start").status_code == 200
    assert "SPEAKING STYLE PROFILE" in call_fakes[-1] and '"um"' in call_fakes[-1]


def test_call_without_learned_style_still_works(client, call_fakes):
    assert client.post("/call/start").status_code == 200
    assert "SPEAKING STYLE PROFILE" not in call_fakes[-1]


def test_call_turn_teaches_style_when_learning_is_on(client, style_store, call_fakes):
    style_store.ensure_profile(KEY, "Tester", learning_enabled=True)
    res = turn(client)
    assert res.status_code == 200, res.text
    assert res.json()["heard"] == SAMPLE_2
    profile = style_store.get_style_profile(KEY)
    assert profile["total_samples"] == 1 and any(p["expression"] == "you know" for p in profile["patterns"])


def test_call_turn_is_not_learned_without_consent(client, style_store, call_fakes):
    assert turn(client).status_code == 200
    assert style_store.get_style_profile(KEY) is None  # never agreed: nothing stored

    style_store.ensure_profile(KEY, "Tester", learning_enabled=False)
    assert turn(client).status_code == 200
    assert style_store.transcript_count(KEY) == 0


def test_style_problem_never_breaks_the_call(client, call_fakes):
    class BrokenStore:
        def get_style_profile(self, key):
            raise RuntimeError("database down")

        def pending_rule_ids(self, *a, **k):
            raise RuntimeError("database down")

    app.dependency_overrides[style_service.get_style_store] = lambda: BrokenStore()
    assert client.post("/call/start").status_code == 200
    assert turn(client).status_code == 200


# ---------- two accounts never share habits ----------

def test_two_users_are_kept_apart(client, style_store, call_fakes):
    alice, bob = str(uuid.uuid4()), str(uuid.uuid4())
    for user_id, lines in [(alice, ["Um, you know, I want to travel.", "Um, you know, I like art."]),
                           (bob, ["Bro, I literally love coding.", "Bro, literally every day."])]:
        style_store.ensure_profile(user_id, None, learning_enabled=True)
        for i, said in enumerate(lines):
            style_store.register_transcript(f"{user_id}-{i}", user_id, said, 6)
        learn(style_store, user_id)

    a = {p["expression"] for p in style_store.get_style_profile(alice)["patterns"]}
    b = {p["expression"] for p in style_store.get_style_profile(bob)["patterns"]}
    assert {"um", "you know"} <= a and not ({"bro", "literally"} & a)
    assert {"bro", "literally"} <= b and not ({"um", "you know"} & b)

    # Bob's call only ever sees Bob's habits.
    app.dependency_overrides[current_user] = lambda: {"id": bob, "email": "b@x.com", "username": "Bob"}
    assert client.post("/call/start").status_code == 200
    assert '"bro"' in call_fakes[-1] and '"um"' not in call_fakes[-1] and '"you know"' not in call_fakes[-1]


# ---------- choosing the future self's voice ----------

@pytest.fixture
def voices(monkeypatch):
    for name, env in voice_ai.VOICE_OPTIONS.items():
        monkeypatch.setenv(env, f"id-{name}")
    monkeypatch.delenv("ASSEMBLYAI_VOICE_ID", raising=False)


def test_voice_list(client, voices):
    assert client.get("/call/voices").json() == {"voices": ["TJ", "Peter", "Lucas"], "default": "TJ"}


def test_no_choice_uses_a_cloned_voice_not_the_stock_one(voices, monkeypatch):
    assert voice_ai.voice_id_for(None) == "id-TJ"
    monkeypatch.setenv("ASSEMBLYAI_VOICE_ID", "id-override")
    assert voice_ai.voice_id_for(None) == "id-override"
    assert voice_ai.voice_id_for("Lucas") == "id-Lucas"


def test_chosen_voice_is_used_for_start_and_turn(client, call_fakes, voices, monkeypatch):
    spoken_with = []
    monkeypatch.setattr(voice_ai, "synthesize", lambda text, voice=None: spoken_with.append(voice) or b"mp3")
    assert client.post("/call/start", json={"voice": "Peter"}).status_code == 200
    res = client.post("/call/turn", files={"audio": ("t.wav", WAV, "audio/wav")},
                      data={"history": "[]", "voice": "Peter"})
    assert res.status_code == 200, res.text
    assert spoken_with == ["Peter", "Peter"]

    assert client.post("/call/start").status_code == 200  # no body still works (default voice)
    assert spoken_with[-1] is None


def test_unknown_voice_is_rejected_before_any_paid_call(client, call_fakes, voices):
    assert client.post("/call/start", json={"voice": "Nobody"}).status_code == 422
    res = client.post("/call/turn", files={"audio": ("t.wav", WAV, "audio/wav")},
                      data={"history": "[]", "voice": "Nobody"})
    assert res.status_code == 422
    assert call_fakes == []  # the LLM was never called


# ---------- scripted moments ----------

from app.models import DimQuestion  # noqa: E402
from app.services import scripted_replies  # noqa: E402


def test_kids_question_has_a_scripted_reply_in_the_call_prompt(client, call_fakes):
    assert client.post("/call/start").status_code == 200
    assert "SCRIPTED MOMENTS" in call_fakes[-1]
    assert "son or a daughter" in call_fakes[-1] and "count your chickens" in call_fakes[-1]


@pytest.mark.parametrize("restricted", [["Family"], ["Relationships"], ["finances", "family"]])
def test_boundaries_switch_the_kids_reply_off(client, call_fakes, monkeypatch, restricted):
    topics = DimQuestion(question_id=uuid.uuid4(), question_code="restricted_topics", category="c",
                         question_text="Topics to avoid?", response_type="multiple_choice", display_order=0)
    monkeypatch.setattr(call, "load_active_questions", lambda db: [topics])
    monkeypatch.setattr(call, "load_latest_answers", lambda db, uid: {topics.question_id: restricted})
    assert client.post("/call/start").status_code == 200
    assert "son or a daughter" not in call_fakes[-1]


def test_unrelated_boundaries_keep_it():
    assert "son or a daughter" in scripted_replies.scripted_section(["Religion", "Finances"])
