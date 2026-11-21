"""Prompt building, the background worker, and the conversation side (LLM is mocked)."""
import json
import threading
import time

import httpx
import pytest

import main as app
from prompts import BASE_SYSTEM_PROMPT, build_system_prompt
from style_learner import StyleLearner
from style_worker import StyleLearningService, StyleWorker


def profile(patterns, total_words=200, total_samples=10, tone=None, notes=None):
    return {
        "voice_id": "voice_a", "display_name": "TJ",
        "total_words": total_words, "total_samples": total_samples,
        "tone_profile": tone or {}, "speaking_habits": {"notes": notes or []},
        "patterns": [
            {"category": c, "expression": e, "occurrence_count": o, "sample_count": s}
            for c, e, o, s in patterns
        ],
    }


# --- dynamic system prompt -----------------------------------------------------------

def test_no_profile_uses_default_prompt():
    assert build_system_prompt(None) == BASE_SYSTEM_PROMPT
    assert build_system_prompt(profile([], total_words=0, total_samples=0)) == BASE_SYSTEM_PROMPT


def test_prompt_includes_frequencies_and_tone():
    prompt = build_system_prompt(profile(
        [("filler_words", "um", 6, 4), ("slang", "bro", 4, 3)],
        tone={"formality": {"informal": 2, "neutral": 1}, "descriptors": {"chill": 2}},
        notes=["Uses bro when joking"],
    ))
    assert prompt.startswith(BASE_SYSTEM_PROMPT)
    assert '"um" (3.0 per 100 words, in 4 of 10 turns)' in prompt
    assert '"bro" (2.0 per 100 words, in 3 of 10 turns)' in prompt
    assert "Formality: informal" in prompt and "chill" in prompt
    assert "Observation: Uses bro when joking" in prompt
    assert "Typical turn length: about 20 words" in prompt
    assert "Do not exaggerate" in prompt


def test_one_off_habits_do_not_reach_the_prompt():
    # "damn" appeared many times but only in one turn: not a habit yet.
    prompt = build_system_prompt(profile([("profanity", "damn", 9, 1), ("slang", "mate", 1, 1)]))
    assert "damn" not in prompt and "mate" not in prompt
    assert prompt == BASE_SYSTEM_PROMPT


def test_prompt_is_compact():
    many = [("slang", f"word{chr(97 + i)}", 10 - i, 3) for i in range(10)]
    prompt = build_system_prompt(profile(many), max_per_category=5)
    assert "worda" in prompt and "worde" in prompt and "wordf" not in prompt


# --- conversation side ----------------------------------------------------------

@pytest.fixture
def mock_gateway(monkeypatch):
    """Replace the LLM Gateway with a fake that records requests."""
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Keep going, you know?"}}]})

    client = httpx.Client(base_url="https://llm-gateway.assemblyai.com", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(app, "llm_client", client)
    monkeypatch.setattr(app, "messages", [{"role": "system", "content": BASE_SYSTEM_PROMPT}])
    return requests


def test_think_uses_latest_profile_and_keeps_history(db, tdir, add_transcript, mock_gateway):
    assert app.think("hi", "voice_a") == "Keep going, you know?"
    assert mock_gateway[0]["messages"][0]["content"] == BASE_SYSTEM_PROMPT

    learner = StyleLearner(db, lambda *a, **k: '{"habits": []}')
    learner.process_transcript(add_transcript("um bro um"))
    learner.process_transcript(add_transcript("um bro yeah"))

    app.think("and now?", "voice_a")
    sent = mock_gateway[1]["messages"]
    assert '"um"' in sent[0]["content"] and '"bro"' in sent[0]["content"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]


def test_think_falls_back_when_database_fails(monkeypatch, mock_gateway):
    def broken():
        raise RuntimeError("db locked")
    monkeypatch.setattr(app, "get_database", broken)
    assert app.think("hi", "voice_a") == "Keep going, you know?"
    assert mock_gateway[0]["messages"][0]["content"] == BASE_SYSTEM_PROMPT


def test_failed_llm_call_does_not_change_history(monkeypatch):
    client = httpx.Client(base_url="https://x", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    monkeypatch.setattr(app, "llm_client", client)
    monkeypatch.setattr(app, "messages", [{"role": "system", "content": BASE_SYSTEM_PROMPT}])
    with pytest.raises(httpx.HTTPStatusError):
        app.think("hi")
    assert len(app.messages) == 1


# --- background worker ----------------------------------------------------------

def make_service(db, tdir, chat=None, batch_size=5):
    learner = StyleLearner(db, chat or (lambda *a, **k: '{"habits": []}'), batch_size=batch_size)
    return StyleLearningService(db, learner, StyleWorker(learner), transcripts_dir=tdir)


def test_record_saves_and_analyses_in_background(db, tdir):
    service = make_service(db, tdir)
    service.start()
    tid = service.record("um bro", "voice_a")
    assert tid
    assert service.worker.wait_until_idle(timeout=5)
    assert db.get_style_profile("voice_a")["total_samples"] == 1
    assert service.shutdown(timeout=5)


def test_empty_transcript_is_not_recorded(db, tdir):
    service = make_service(db, tdir)
    assert service.record("   ", "voice_a") is None
    assert not tdir.exists()


def test_record_never_raises(db, tdir, monkeypatch):
    service = make_service(db, tdir)
    monkeypatch.setattr("style_worker.save_transcript", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    assert service.record("hello", "voice_a") is None


def test_slow_analysis_does_not_delay_the_reply(db, tdir, mock_gateway, monkeypatch):
    """A deliberately slow analyzer must not slow down recording or the LLM reply."""
    release = threading.Event()
    service = make_service(db, tdir)
    original = service.learner.process_transcript

    def slow_process(tid):
        release.wait(10)  # stuck until the test lets it go
        return original(tid)

    monkeypatch.setattr(service.learner, "process_transcript", slow_process)
    service.start()

    started = time.perf_counter()
    service.record("um bro", "voice_a")
    reply = app.think("um bro", "voice_a")
    elapsed = time.perf_counter() - started

    assert reply == "Keep going, you know?"
    assert elapsed < 1.0
    assert db.get_style_profile("voice_a")["total_samples"] == 0  # analysis still waiting

    release.set()
    assert service.worker.wait_until_idle(timeout=5)
    assert db.get_style_profile("voice_a")["total_samples"] == 1
    service.shutdown(timeout=5)


def test_full_queue_keeps_task_pending_for_later(db, tdir):
    learner = StyleLearner(db, lambda *a, **k: '{"habits": []}')
    service = StyleLearningService(db, learner, StyleWorker(learner, maxsize=1), transcripts_dir=tdir)
    # Worker not started, so the queue fills up.
    service.record("bro", "voice_a")
    service.record("mate", "voice_a")
    assert len(db.pending_rule_ids()) == 2

    # On the next start, recovery picks up everything that is still pending.
    restarted = make_service(db, tdir)
    restarted.start()
    assert restarted.worker.wait_until_idle(timeout=5)
    assert db.get_style_profile("voice_a")["total_samples"] == 2
    restarted.shutdown(timeout=5)


def test_worker_survives_failing_tasks(db, tdir, monkeypatch):
    service = make_service(db, tdir)
    calls = []

    def flaky(tid):
        calls.append(tid)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return True

    monkeypatch.setattr(service.learner, "process_transcript", flaky)
    service.start()
    service.worker.submit("a")
    service.worker.submit("b")
    assert service.worker.wait_until_idle(timeout=5)
    assert calls == ["a", "b"]
    assert service.shutdown(timeout=5)


def test_shutdown_finishes_queued_work(db, tdir):
    service = make_service(db, tdir)
    service.start()
    for i in range(5):
        service.record(f"bro number {i}", "voice_a")
    assert service.shutdown(timeout=10)
    assert db.get_style_profile("voice_a")["total_samples"] == 5


def test_blank_consent_answer_asks_again(db, monkeypatch):
    answers = iter(["", "  ", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert app.ask_learning_consent(db, "voice_a") is True
    assert db.get_learning_consent("voice_a") is True


def test_saved_no_is_reported_and_learn_flag_asks_again(db, monkeypatch, capsys):
    db.set_learning_consent("voice_a", False)
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("should not ask"))
    assert app.ask_learning_consent(db, "voice_a") is False
    assert "--learn" in capsys.readouterr().out

    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    assert app.ask_learning_consent(db, "voice_a", ask_again=True) is True
    assert db.get_learning_consent("voice_a") is True


def test_database_keeps_the_text_not_a_local_path(db, tdir):
    service = make_service(db, tdir)
    tid = service.record("  um,   bro\tyeah ", "voice_a")
    with db._read() as conn:
        row = dict(conn.execute("SELECT * FROM fact_transcript WHERE transcript_id = ?", (tid,)).fetchone())
    assert row["text"] == "um, bro yeah"
    assert "file_path" not in row


def test_browser_roles_cannot_read_style_tables(db, add_transcript):
    """On Supabase, the anon/authenticated roles behind the public web API must see nothing."""
    if db.path is not None:
        pytest.skip("PostgreSQL only (set VOICE_TEST_PG_URL)")
    import psycopg

    from database import STYLE_TABLES, PostgresStyleDatabase

    add_transcript("um bro")
    with psycopg.connect(db.pool.conninfo, autocommit=True) as conn:
        conn.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') "
                     "THEN CREATE ROLE anon NOLOGIN; END IF; END $$")
        # Like Supabase: the browser role can use the schema and was granted the tables.
        conn.execute(f"GRANT USAGE ON SCHEMA {db.schema} TO anon")
        conn.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {db.schema} TO anon")
    PostgresStyleDatabase(db.pool.conninfo, schema=db.schema).close()  # setup runs again and locks the tables

    with psycopg.connect(db.pool.conninfo) as conn:
        for table in STYLE_TABLES:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE anon")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute(f"SELECT * FROM {db.schema}.{table}")
        rls = conn.execute("SELECT bool_and(relrowsecurity) FROM pg_class WHERE relnamespace = %s::regnamespace "
                           "AND relname = ANY(%s)", (db.schema, list(STYLE_TABLES))).fetchone()[0]
        assert rls is True


def test_think_sends_questionnaire_answers(mock_gateway):
    answers = [{"code": "age", "category": "About You", "question": "How old are you?", "answer": "24", "value": 24},
               {"code": "goal", "category": "Values", "question": "Biggest goal?", "answer": "Run a cafe",
                "value": "Run a cafe"}]
    app.think("hi", None, answers)
    system = mock_gateway[0]["messages"][0]["content"]
    assert "you are about 34" in system and '"Run a cafe"' in system


def test_skip_questions_and_sqlite_mode_skip_login(monkeypatch):
    monkeypatch.setattr(app, "setup_profile", lambda db, **kw: pytest.fail("should not log in"))
    assert app.start_profile(skip_questions=True) == (None, [])
    monkeypatch.setattr(app.config, "STYLE_DB", "sqlite")
    assert app.start_profile(skip_questions=False) == (None, [])


def test_failed_login_stops_the_app(monkeypatch):
    from user_profile import LoginError, LoginUnavailable
    monkeypatch.setattr(app.config, "STYLE_DB", "supabase")
    monkeypatch.setattr(app, "get_database", lambda: object())

    def wrong(db, **kwargs):
        raise LoginError("Too many failed login attempts.")
    monkeypatch.setattr(app, "setup_profile", wrong)
    assert app.start_profile(False) is None

    def offline(db, **kwargs):
        raise LoginUnavailable("Could not reach Supabase.")
    monkeypatch.setattr(app, "setup_profile", offline)
    assert app.start_profile(False) == (None, [])


def test_style_belongs_to_the_logged_in_user():
    assert app.style_key_for({"id": "user-1", "display_name": "Lucas"}, "voice_tj") == ("user-1", "Lucas")
    assert app.style_key_for({"id": "user-1", "display_name": None}, "voice_tj") == ("user-1", "you")
    assert app.style_key_for(None, "voice_tj") == ("voice_tj", "TJ")


def test_spoken_website_answers_are_learned_before_the_chat(db, monkeypatch, capsys):
    """Answers spoken on the website wait in the database; startup analyses them first."""
    db.set_learning_consent("user-1", True)  # the website does this when answers are spoken
    db.register_transcript("q1", "user-1", "um so like I wanna build stuff bro", 8)
    db.register_transcript("q2", "user-1", "um honestly bro I dunno", 5)
    monkeypatch.setattr(app, "chat", lambda *a, **k: '{"habits": []}')

    service, learning = app.start_style_learning("user-1", "Lucas", no_learning=False)
    try:
        assert learning is True  # no consent question: already agreed on the website
        assert "Learning how you talk from 2 earlier answers" in capsys.readouterr().out
        style = db.get_style_profile("user-1")
        assert style["total_samples"] == 2
        assert {p["expression"] for p in style["patterns"]} >= {"um", "bro"}
        # ...so the very first reply already uses the habits.
        prompt = app.personalised_system_prompt("user-1")
        assert '"um"' in prompt and '"bro"' in prompt
    finally:
        service.shutdown(timeout=5)
