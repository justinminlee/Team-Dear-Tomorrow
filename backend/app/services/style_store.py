"""Reads and writes for speaking style learning, on the public.* style tables.

Port of VOICE/database.py (StyleDatabase): the same tables and the same status values,
so the website backend and the VOICE app can both analyse samples without double counting:
    public.dim_voice_style, public.fact_transcript,
    public.fact_speaking_pattern, public.fact_transcript_pattern

Every write runs in one transaction. Task claims are conditional UPDATEs, so two
workers can never analyse the same transcript, and counts are only ever added.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import DimVoiceStyle, FactSpeakingPattern, FactTranscript, FactTranscriptPattern

PENDING, PROCESSING, COMPLETED, FAILED = "pending", "processing", "completed", "failed"
MAX_ATTEMPTS = 3

style = DimVoiceStyle.__table__
transcripts = FactTranscript.__table__
patterns = FactSpeakingPattern.__table__
transcript_patterns = FactTranscriptPattern.__table__


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def user_style_key(user_id: str) -> str:
    """The voice_id key of a user's speaking style profile: the user's id itself.

    Same key as backend/app/api/voice_answers.py and the VOICE app (logged in), so
    samples from the website and the terminal build one profile per user.
    """
    return str(user_id)


def merge_tone_votes(existing: dict | None, new_votes: dict) -> dict:
    """Add one batch's tone observations to the accumulated vote counts.

    existing: {"formality": {"informal": 3}, "descriptors": {"casual": 2}, ...}
    new_votes: {"formality": "informal", "descriptors": ["casual", "warm"], ...}
    """
    merged = {key: dict(value) for key, value in (existing or {}).items()}
    for key, value in new_votes.items():
        bucket = merged.setdefault(key, {})
        for v in value if isinstance(value, list) else [value]:
            bucket[v] = bucket.get(v, 0) + 1
    return merged


class StyleStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _insert(self, conn, table):
        """INSERT that supports ON CONFLICT DO NOTHING on both PostgreSQL and SQLite (tests)."""
        return (pg_insert if conn.dialect.name == "postgresql" else sqlite_insert)(table)

    # --- profiles -------------------------------------------------------------

    def _ensure_profile(self, conn, voice_id: str, display_name: str | None, now: datetime):
        conn.execute(
            self._insert(conn, style)
            .values(voice_id=voice_id, display_name=display_name, total_words=0, total_samples=0,
                    tone_profile={}, speaking_habits={}, created_at=now, updated_at=now)
            .on_conflict_do_nothing(index_elements=["voice_id"])
        )

    def ensure_profile(self, voice_id: str, display_name: str | None = None, learning_enabled: bool | None = None):
        """Create the profile if missing; refresh the name and consent when given."""
        now = utcnow()
        with self.engine.begin() as conn:
            self._ensure_profile(conn, voice_id, display_name, now)
            changes: dict[str, Any] = {}
            if display_name:
                changes["display_name"] = display_name
            if learning_enabled is not None:
                changes["learning_enabled"] = 1 if learning_enabled else 0
            if changes:
                conn.execute(update(style).where(style.c.voice_id == voice_id).values(**changes, updated_at=now))

    def get_style_profile(self, voice_id: str) -> dict | None:
        """The latest committed profile, or None if this key has none."""
        with self.engine.connect() as conn:
            profile = conn.execute(select(style).where(style.c.voice_id == voice_id)).mappings().first()
            if profile is None:
                return None
            rows = conn.execute(
                select(patterns.c.category, patterns.c.expression, patterns.c.source,
                       patterns.c.context_dependent, patterns.c.occurrence_count, patterns.c.sample_count)
                .where(patterns.c.voice_id == voice_id)
                .order_by(patterns.c.occurrence_count.desc(), patterns.c.expression)
            ).mappings().all()
        return {
            "voice_id": profile["voice_id"],
            "display_name": profile["display_name"],
            "total_words": profile["total_words"],
            "total_samples": profile["total_samples"],
            "tone_profile": profile["tone_profile"] or {},
            "speaking_habits": profile["speaking_habits"] or {},
            "learning_enabled": profile["learning_enabled"],
            "patterns": [dict(r) for r in rows],
        }

    def learned_vocabulary(self, voice_id: str) -> list[tuple[str, str]]:
        """Expressions the LLM discovered that the rules can now count directly."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(patterns.c.category, patterns.c.expression).where(
                    patterns.c.voice_id == voice_id, patterns.c.source == "llm", patterns.c.context_dependent == 0
                )
            ).all()
        return [(r.category, r.expression) for r in rows]

    # --- transcripts and rule-based analysis -------------------------------------

    def register_transcript(self, transcript_id: str, voice_id: str, text: str, word_count: int,
                            display_name: str | None = None) -> bool:
        """Store what the user said as pending analysis. False if it was already registered."""
        now = utcnow()
        with self.engine.begin() as conn:
            self._ensure_profile(conn, voice_id, display_name, now)
            inserted = conn.execute(
                self._insert(conn, transcripts)
                .values(transcript_id=transcript_id, voice_id=voice_id, text=text, word_count=word_count,
                        analysis_status=PENDING, llm_analysis_status=PENDING, rule_attempts=0,
                        llm_attempts=0, created_at=now)
                .on_conflict_do_nothing(index_elements=["transcript_id"])
                .returning(transcripts.c.transcript_id)
            ).first()
        return inserted is not None

    def claim_rule_task(self, transcript_id: str, max_attempts: int = MAX_ATTEMPTS) -> dict | None:
        """Mark a transcript as being analysed. Its row, or None if taken, done or out of retries."""
        with self.engine.begin() as conn:
            result = conn.execute(
                update(transcripts)
                .where(transcripts.c.transcript_id == transcript_id,
                       transcripts.c.analysis_status.in_([PENDING, FAILED]),
                       transcripts.c.rule_attempts < max_attempts)
                .values(analysis_status=PROCESSING, rule_attempts=transcripts.c.rule_attempts + 1)
            )
            if result.rowcount != 1:
                return None
            row = conn.execute(select(transcripts).where(transcripts.c.transcript_id == transcript_id)).mappings().first()
        return dict(row)

    def complete_rule_task(self, transcript_id: str, observations: Iterable[tuple]) -> bool:
        """Save rule results and mark the transcript done, in one transaction.

        observations: (category, expression, count, source, context_dependent).
        """
        now = utcnow()
        with self.engine.begin() as conn:
            row = conn.execute(
                select(transcripts.c.voice_id, transcripts.c.word_count, transcripts.c.analysis_status)
                .where(transcripts.c.transcript_id == transcript_id)
            ).first()
            if row is None or row.analysis_status != PROCESSING:
                return False
            for category, expression, count, source, context_dependent in observations:
                self._record_pattern(conn, transcript_id, row.voice_id, category, expression,
                                     count, source, context_dependent, now)
            conn.execute(
                update(style).where(style.c.voice_id == row.voice_id).values(
                    total_words=style.c.total_words + row.word_count,
                    total_samples=style.c.total_samples + 1,
                    updated_at=now,
                )
            )
            conn.execute(
                update(transcripts).where(transcripts.c.transcript_id == transcript_id)
                .values(analysis_status=COMPLETED, processed_at=now)
            )
        return True

    def fail_rule_task(self, transcript_id: str):
        with self.engine.begin() as conn:
            conn.execute(
                update(transcripts)
                .where(transcripts.c.transcript_id == transcript_id, transcripts.c.analysis_status == PROCESSING)
                .values(analysis_status=FAILED)
            )

    def _record_pattern(self, conn, transcript_id, voice_id, category, expression, count,
                        source, context_dependent, now) -> bool:
        """Add one transcript's count for one expression to the running totals.

        Does nothing if this transcript already contributed this expression, which makes
        retries and rule/LLM overlap safe.
        """
        if count <= 0:
            return False
        existing = conn.execute(
            select(patterns.c.id, patterns.c.category)
            .where(patterns.c.voice_id == voice_id, patterns.c.expression == expression)
            .order_by(patterns.c.id).limit(1)
        ).first()
        category = existing.category if existing else category  # one category per expression

        # RETURNING tells us whether the row was new. (rowcount is -1 for this statement
        # on PostgreSQL/psycopg, so it can't be used.)
        inserted = conn.execute(
            self._insert(conn, transcript_patterns)
            .values(transcript_id=transcript_id, expression=expression, category=category, occurrence_count=count)
            .on_conflict_do_nothing(index_elements=["transcript_id", "expression"])
            .returning(transcript_patterns.c.transcript_id)
        ).first()
        if inserted is None:
            return False

        if existing:
            conn.execute(
                update(patterns).where(patterns.c.id == existing.id).values(
                    occurrence_count=patterns.c.occurrence_count + count,
                    sample_count=patterns.c.sample_count + 1,
                    last_seen_at=now,
                )
            )
        else:
            conn.execute(
                patterns.insert().values(
                    voice_id=voice_id, category=category, expression=expression, source=source,
                    context_dependent=1 if context_dependent else 0, occurrence_count=count,
                    sample_count=1, first_seen_at=now, last_seen_at=now,
                )
            )
        return True

    def pending_rule_ids(self, voice_id: str, max_attempts: int = MAX_ATTEMPTS) -> list[str]:
        """Transcripts of one key still waiting for (or retrying) rule analysis, oldest first."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(transcripts.c.transcript_id)
                .where(transcripts.c.voice_id == voice_id,
                       transcripts.c.analysis_status.in_([PENDING, FAILED]),
                       transcripts.c.rule_attempts < max_attempts)
                .order_by(transcripts.c.created_at, transcripts.c.transcript_id)
            ).all()
        return [r.transcript_id for r in rows]

    # --- LLM batch analysis -----------------------------------------------------

    def llm_backlog(self, voice_id: str, max_attempts: int = MAX_ATTEMPTS) -> list[dict]:
        """Transcripts that passed rule analysis and still need LLM analysis, oldest first."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(transcripts.c.transcript_id, transcripts.c.text)
                .where(transcripts.c.voice_id == voice_id,
                       transcripts.c.analysis_status == COMPLETED,
                       transcripts.c.llm_analysis_status.in_([PENDING, FAILED]),
                       transcripts.c.llm_attempts < max_attempts)
                .order_by(transcripts.c.created_at, transcripts.c.transcript_id)
            ).mappings().all()
        return [dict(r) for r in rows]

    def claim_llm_batch(self, transcript_ids: list[str]) -> list[str]:
        claimed = []
        with self.engine.begin() as conn:
            for tid in transcript_ids:
                result = conn.execute(
                    update(transcripts)
                    .where(transcripts.c.transcript_id == tid,
                           transcripts.c.llm_analysis_status.in_([PENDING, FAILED]))
                    .values(llm_analysis_status=PROCESSING, llm_attempts=transcripts.c.llm_attempts + 1)
                )
                if result.rowcount == 1:
                    claimed.append(tid)
        return claimed

    def complete_llm_batch(self, voice_id: str, transcript_ids: list[str], observations: Iterable[tuple],
                           tone: dict | None = None, notes: list[str] | None = None) -> int:
        """Save one LLM batch and mark its transcripts done, in one transaction.

        observations: (transcript_id, category, expression, count, context_dependent).
        """
        now = utcnow()
        with self.engine.begin() as conn:
            valid = set(conn.execute(
                select(transcripts.c.transcript_id).where(
                    transcripts.c.voice_id == voice_id,
                    transcripts.c.llm_analysis_status == PROCESSING,
                    transcripts.c.transcript_id.in_(transcript_ids),
                )
            ).scalars())
            for tid, category, expression, count, context_dependent in observations:
                if tid in valid:
                    self._record_pattern(conn, tid, voice_id, category, expression, count,
                                         "llm", context_dependent, now)

            profile = conn.execute(
                select(style.c.tone_profile, style.c.speaking_habits).where(style.c.voice_id == voice_id)
            ).first()
            tone_profile = dict(profile.tone_profile or {})
            habits = dict(profile.speaking_habits or {})
            if tone:
                tone_profile = merge_tone_votes(tone_profile, tone)
            if notes:
                habits["notes"] = list(notes)[:3]
            conn.execute(
                update(style).where(style.c.voice_id == voice_id)
                .values(tone_profile=tone_profile, speaking_habits=habits, updated_at=now)
            )
            if valid:
                conn.execute(
                    update(transcripts).where(transcripts.c.transcript_id.in_(valid))
                    .values(llm_analysis_status=COMPLETED, llm_processed_at=now)
                )
        return len(valid)

    def fail_llm_batch(self, transcript_ids: list[str]):
        with self.engine.begin() as conn:
            conn.execute(
                update(transcripts)
                .where(transcripts.c.transcript_id.in_(transcript_ids),
                       transcripts.c.llm_analysis_status == PROCESSING)
                .values(llm_analysis_status=FAILED)
            )

    def transcript_count(self, voice_id: str) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                select(func.count()).select_from(transcripts).where(transcripts.c.voice_id == voice_id)
            ).scalar_one()
