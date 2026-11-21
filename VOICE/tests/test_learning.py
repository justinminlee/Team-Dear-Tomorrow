"""Database, merging and continuous learning."""
import json

import pytest

from database import StyleDatabase
from style_learner import StyleLearner, frequency_per_100_words


def counts(db, voice_id="voice_a"):
    """{category: {expression: occurrence_count}} for a voice."""
    out = {}
    for p in db.get_style_profile(voice_id)["patterns"]:
        out.setdefault(p["category"], {})[p["expression"]] = p["occurrence_count"]
    return out


def learner_for(db, tdir, chat=None, batch_size=5):
    return StyleLearner(db, chat or (lambda *a, **k: '{"habits": []}'), batch_size=batch_size)


def test_spec_merge_example(db, tdir, add_transcript):
    """Existing {um: 12, uh: 5, bro: 8} + new {um: 2, bro: 1, mate: 1} -> {um: 14, uh: 5, bro: 9, mate: 1}."""
    learner = learner_for(db, tdir)
    learner.process_transcript(add_transcript("um " * 12 + "uh " * 5 + "bro " * 8))
    learner.process_transcript(add_transcript("um um bro mate"))
    result = counts(db)
    assert result["filler_words"] == {"um": 14, "uh": 5}
    assert result["slang"] == {"bro": 9, "mate": 1}


def test_sample_count_tracks_distinct_transcripts(db, tdir, add_transcript):
    learner = learner_for(db, tdir)
    learner.process_transcript(add_transcript("bro bro bro bro"))
    learner.process_transcript(add_transcript("hey bro"))
    bro = next(p for p in db.get_style_profile("voice_a")["patterns"] if p["expression"] == "bro")
    assert bro["occurrence_count"] == 5 and bro["sample_count"] == 2


def test_profile_totals_and_frequency(db, tdir, add_transcript):
    learner = learner_for(db, tdir)
    learner.process_transcript(add_transcript("um I think so"))   # 4 words
    learner.process_transcript(add_transcript("um um okay then yes ok"))  # 6 words
    profile = db.get_style_profile("voice_a")
    assert profile["total_words"] == 10 and profile["total_samples"] == 2
    assert frequency_per_100_words(3, profile["total_words"]) == pytest.approx(30.0)
    assert frequency_per_100_words(1, 0) == 0.0


def test_data_persists_across_restarts(tmp_path, tdir, add_transcript, db):
    learner_for(db, tdir).process_transcript(add_transcript("bro"))
    if db.path is None:  # PostgreSQL: open a second, independent connection pool on the same schema
        from database import PostgresStyleDatabase
        reopened = PostgresStyleDatabase(db.pool.conninfo, schema=db.schema)
    else:
        reopened = StyleDatabase(db.path)
    assert counts(reopened)["slang"] == {"bro": 1}
    reopened.close()


def test_voices_are_isolated(db, tdir, add_transcript):
    learner = learner_for(db, tdir)
    learner.process_transcript(add_transcript("bro bro", voice_id="voice_a"))
    learner.process_transcript(add_transcript("mate", voice_id="voice_b"))
    assert counts(db, "voice_a") == {"slang": {"bro": 2}}
    assert counts(db, "voice_b") == {"slang": {"mate": 1}}
    assert db.get_style_profile("voice_c") is None


def test_same_transcript_is_never_counted_twice(db, tdir, add_transcript):
    learner = learner_for(db, tdir)
    tid = add_transcript("bro")
    assert learner.process_transcript(tid) is True
    assert learner.process_transcript(tid) is False
    assert counts(db)["slang"] == {"bro": 1}
    assert db.get_style_profile("voice_a")["total_samples"] == 1


def test_duplicate_registration_is_ignored(db, tdir):
    assert db.register_transcript("t1", "voice_a", "um bro yeah", 3) is True
    assert db.register_transcript("t1", "voice_a", "um bro yeah", 3) is False


def test_interrupted_tasks_are_recovered(db, tdir, add_transcript):
    tid = add_transcript("bro")
    assert db.claim_rule_task(tid)  # simulate a crash mid-analysis: left "processing"
    assert db.pending_rule_ids() == []
    db.reset_interrupted()
    assert db.pending_rule_ids() == [tid]
    learner_for(db, tdir).process_transcript(tid)
    assert counts(db)["slang"] == {"bro": 1}


def test_failed_rule_task_can_retry(db, tdir, add_transcript, monkeypatch):
    learner = learner_for(db, tdir)
    tid = add_transcript("bro")
    monkeypatch.setattr("style_learner.style_analyzer.extract_rule_patterns",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert learner.process_transcript(tid) is False
    monkeypatch.undo()
    assert learner.process_transcript(tid) is True
    assert counts(db)["slang"] == {"bro": 1}


def test_reset_profile_deletes_everything_for_one_voice(db, tdir, add_transcript):
    learner = learner_for(db, tdir)
    learner.process_transcript(add_transcript("bro", "voice_a"))
    learner.process_transcript(add_transcript("mate", "voice_b"))
    assert db.reset_profile("voice_a") == 1
    assert db.get_style_profile("voice_a") is None
    assert counts(db, "voice_b") == {"slang": {"mate": 1}}


def test_consent_is_remembered_per_voice(db):
    assert db.get_learning_consent("voice_a") is None
    db.set_learning_consent("voice_a", True)
    db.set_learning_consent("voice_b", False)
    assert db.get_learning_consent("voice_a") is True
    assert db.get_learning_consent("voice_b") is False


# --- LLM batches -------------------------------------------------------------------

def llm_reply(*habits, tone=None, notes=None):
    return json.dumps({"habits": list(habits), "tone": tone or {}, "notes": notes or []})


def test_llm_runs_only_after_a_full_batch(db, tdir, add_transcript, fake_chat):
    chat = fake_chat()
    learner = learner_for(db, tdir, chat, batch_size=3)
    learner.process_transcript(add_transcript("one"))
    learner.process_transcript(add_transcript("two"))
    assert chat.calls == []
    learner.process_transcript(add_transcript("three"))
    assert len(chat.calls) == 1


def test_llm_discovers_new_expressions_and_tone(db, tdir, add_transcript, fake_chat):
    reply = llm_reply(
        {"category": "slang", "expression": "innit", "counts": {"T1": 1, "T2": 1}},
        tone={"formality": "informal", "descriptors": ["chill"]},
        notes=["Says innit at the end of questions"],
    )
    learner = learner_for(db, tdir, fake_chat(reply), batch_size=2)
    learner.process_transcript(add_transcript("cold innit"))
    learner.process_transcript(add_transcript("good innit"))
    profile = db.get_style_profile("voice_a")
    innit = next(p for p in profile["patterns"] if p["expression"] == "innit")
    assert (innit["occurrence_count"], innit["sample_count"], innit["source"]) == (2, 2, "llm")
    assert profile["tone_profile"] == {"formality": {"informal": 1}, "descriptors": {"chill": 1}}
    assert profile["speaking_habits"]["notes"] == ["Says innit at the end of questions"]

    # Once discovered, the rules count it in new transcripts without waiting for the LLM.
    learner.process_transcript(add_transcript("innit"))
    assert counts(db)["slang"]["innit"] == 3


def test_rule_and_llm_overlap_is_not_double_counted(db, tdir, add_transcript, fake_chat):
    reply = llm_reply({"category": "slang", "expression": "bro", "counts": {"T1": 2}},
                      {"category": "profanity", "expression": "um", "counts": {"T1": 1}})
    learner = learner_for(db, tdir, fake_chat(reply), batch_size=1)
    learner.process_transcript(add_transcript("um bro bro"))
    assert counts(db) == {"slang": {"bro": 2}, "filler_words": {"um": 1}}


def test_failed_llm_batch_retries_without_inflating_counts(db, tdir, add_transcript, fake_chat):
    good = llm_reply({"category": "filler_words", "expression": "like", "context_dependent": True,
                      "counts": {"T1": 1, "T2": 1}})
    chat = fake_chat(RuntimeError("network down"), "not json at all", good)
    learner = learner_for(db, tdir, chat, batch_size=2)
    learner.process_transcript(add_transcript("it was like good"))
    learner.process_transcript(add_transcript("like whatever"))  # batch 1: network error
    assert "filler_words" not in counts(db)

    assert learner.run_llm_batches("voice_a") == 0  # batch 2: invalid JSON
    assert learner.run_llm_batches("voice_a") == 1  # batch 3: success
    assert learner.run_llm_batches("voice_a") == 0  # nothing left to do
    assert counts(db)["filler_words"] == {"like": 2}
    assert db.get_style_profile("voice_a")["total_samples"] == 2


def test_llm_gives_up_after_max_attempts(db, tdir, add_transcript, fake_chat):
    chat = fake_chat(*[RuntimeError("down")] * 10)
    learner = StyleLearner(db, chat, batch_size=1, max_attempts=2)
    learner.process_transcript(add_transcript("hello"))
    learner.run_llm_batches("voice_a")
    learner.run_llm_batches("voice_a")
    assert len(chat.calls) == 2
    assert db.llm_backlog("voice_a", max_attempts=2) == []
