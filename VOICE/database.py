"""SQLite storage for speaking style profiles, learned patterns and transcript bookkeeping.

Every method opens its own short-lived connection, so the conversation loop and the
background style worker can use the database at the same time. WAL mode lets reads
continue while the worker writes, and every multi-row update runs in one transaction.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import config

PENDING = "pending"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"

SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    voice_id          TEXT PRIMARY KEY,
    display_name      TEXT,
    total_words       INTEGER NOT NULL DEFAULT 0,
    total_samples     INTEGER NOT NULL DEFAULT 0,
    tone_profile      TEXT NOT NULL DEFAULT '{}',   -- JSON: accumulated tone votes
    speaking_habits   TEXT NOT NULL DEFAULT '{}',   -- JSON: latest contextual notes
    learning_enabled  INTEGER,                      -- NULL = not asked yet, 0 = no, 1 = yes
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS speaking_patterns (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id           TEXT NOT NULL REFERENCES voice_profiles(voice_id) ON DELETE CASCADE,
    category           TEXT NOT NULL,
    expression         TEXT NOT NULL,
    source             TEXT NOT NULL DEFAULT 'rule',  -- 'rule' or 'llm' (discovered by the LLM)
    context_dependent  INTEGER NOT NULL DEFAULT 0,    -- 1 for words like "like" that are only sometimes habits
    occurrence_count   INTEGER NOT NULL DEFAULT 0,
    sample_count       INTEGER NOT NULL DEFAULT 0,    -- number of distinct transcripts containing it
    first_seen_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL,
    UNIQUE (voice_id, category, expression)
);
CREATE INDEX IF NOT EXISTS idx_patterns_voice_expression ON speaking_patterns(voice_id, expression);

CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id        TEXT PRIMARY KEY,
    voice_id             TEXT NOT NULL REFERENCES voice_profiles(voice_id) ON DELETE CASCADE,
    file_path            TEXT NOT NULL,
    word_count           INTEGER NOT NULL,
    analysis_status      TEXT NOT NULL DEFAULT 'pending',
    llm_analysis_status  TEXT NOT NULL DEFAULT 'pending',
    rule_attempts        INTEGER NOT NULL DEFAULT 0,
    llm_attempts         INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL,
    processed_at         TEXT,
    llm_processed_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_transcripts_status ON transcripts(voice_id, analysis_status, llm_analysis_status);

-- One row per (transcript, expression). This is what stops double counting:
-- an expression found by both the rules and the LLM, or by a retried batch,
-- is only ever added to the totals once per transcript.
CREATE TABLE IF NOT EXISTS transcript_patterns (
    transcript_id     TEXT NOT NULL REFERENCES transcripts(transcript_id) ON DELETE CASCADE,
    expression        TEXT NOT NULL,
    category          TEXT NOT NULL,
    occurrence_count  INTEGER NOT NULL,
    PRIMARY KEY (transcript_id, expression)
);
"""


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class StyleDatabase:
    """All reads and writes for speaking style learning."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    # --- connection helpers -------------------------------------------------

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)  # we manage transactions
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def _read(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _write(self):
        """Run a block in one IMMEDIATE transaction: all of it is saved, or none of it."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # --- profiles -----------------------------------------------------------

    def ensure_profile(self, voice_id, display_name=None):
        """Create an empty profile for an existing Voice ID if it doesn't have one yet."""
        now = utcnow()
        with self._write() as conn:
            self._ensure_profile(conn, voice_id, display_name, now)
            if display_name:
                conn.execute(
                    "UPDATE voice_profiles SET display_name = ? WHERE voice_id = ? AND display_name IS NOT ?",
                    (display_name, voice_id, display_name),
                )

    @staticmethod
    def _ensure_profile(conn, voice_id, display_name, now):
        conn.execute(
            "INSERT OR IGNORE INTO voice_profiles (voice_id, display_name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (voice_id, display_name, now, now),
        )

    def get_learning_consent(self, voice_id):
        """Return True/False if the user answered the consent question, or None if not asked yet."""
        with self._read() as conn:
            row = conn.execute(
                "SELECT learning_enabled FROM voice_profiles WHERE voice_id = ?", (voice_id,)
            ).fetchone()
        if row is None or row["learning_enabled"] is None:
            return None
        return bool(row["learning_enabled"])

    def set_learning_consent(self, voice_id, enabled):
        now = utcnow()
        with self._write() as conn:
            self._ensure_profile(conn, voice_id, None, now)
            conn.execute(
                "UPDATE voice_profiles SET learning_enabled = ?, updated_at = ? WHERE voice_id = ?",
                (1 if enabled else 0, now, voice_id),
            )

    def get_style_profile(self, voice_id):
        """Return the latest committed profile for one voice, or None if it has none."""
        with self._read() as conn:
            profile = conn.execute(
                "SELECT * FROM voice_profiles WHERE voice_id = ?", (voice_id,)
            ).fetchone()
            if profile is None:
                return None
            patterns = conn.execute(
                "SELECT category, expression, source, context_dependent, occurrence_count, sample_count "
                "FROM speaking_patterns WHERE voice_id = ? ORDER BY occurrence_count DESC, expression",
                (voice_id,),
            ).fetchall()
        return {
            "voice_id": profile["voice_id"],
            "display_name": profile["display_name"],
            "total_words": profile["total_words"],
            "total_samples": profile["total_samples"],
            "tone_profile": json.loads(profile["tone_profile"] or "{}"),
            "speaking_habits": json.loads(profile["speaking_habits"] or "{}"),
            "patterns": [dict(p) for p in patterns],
        }

    def learned_vocabulary(self, voice_id):
        """Expressions the LLM discovered for this voice that the rules can now count directly."""
        with self._read() as conn:
            rows = conn.execute(
                "SELECT category, expression FROM speaking_patterns "
                "WHERE voice_id = ? AND source = 'llm' AND context_dependent = 0",
                (voice_id,),
            ).fetchall()
        return [(r["category"], r["expression"]) for r in rows]

    def reset_profile(self, voice_id):
        """Delete everything learned for one voice. Returns how many transcripts were removed."""
        with self._write() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM transcripts WHERE voice_id = ?", (voice_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM voice_profiles WHERE voice_id = ?", (voice_id,))  # cascades
        return count

    # --- transcripts and rule-based analysis ----------------------------------

    def register_transcript(self, transcript_id, voice_id, file_path, word_count):
        """Record a saved transcript as pending analysis. Returns False if it was already registered."""
        now = utcnow()
        with self._write() as conn:
            self._ensure_profile(conn, voice_id, None, now)
            cur = conn.execute(
                "INSERT OR IGNORE INTO transcripts (transcript_id, voice_id, file_path, word_count, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (transcript_id, voice_id, str(file_path), word_count, now),
            )
        return cur.rowcount == 1

    def claim_rule_task(self, transcript_id, max_attempts=config.STYLE_MAX_ATTEMPTS):
        """Mark a transcript as being analysed. Returns its row, or None if someone else has it or it's done."""
        with self._write() as conn:
            cur = conn.execute(
                "UPDATE transcripts SET analysis_status = ?, rule_attempts = rule_attempts + 1 "
                "WHERE transcript_id = ? AND analysis_status IN (?, ?) AND rule_attempts < ?",
                (PROCESSING, transcript_id, PENDING, FAILED, max_attempts),
            )
            if cur.rowcount != 1:
                return None
            row = conn.execute("SELECT * FROM transcripts WHERE transcript_id = ?", (transcript_id,)).fetchone()
        return dict(row)

    def complete_rule_task(self, transcript_id, observations):
        """Save rule-based results and mark the transcript done, all in one transaction.

        observations: list of (category, expression, count, source, context_dependent).
        Counts are added to the existing totals, never replacing them.
        """
        now = utcnow()
        with self._write() as conn:
            row = conn.execute(
                "SELECT voice_id, word_count, analysis_status FROM transcripts WHERE transcript_id = ?",
                (transcript_id,),
            ).fetchone()
            if row is None or row["analysis_status"] != PROCESSING:
                return False
            for category, expression, count, source, context_dependent in observations:
                self._record_pattern(conn, transcript_id, row["voice_id"], category, expression,
                                     count, source, context_dependent, now)
            conn.execute(
                "UPDATE voice_profiles SET total_words = total_words + ?, total_samples = total_samples + 1, "
                "updated_at = ? WHERE voice_id = ?",
                (row["word_count"], now, row["voice_id"]),
            )
            conn.execute(
                "UPDATE transcripts SET analysis_status = ?, processed_at = ? WHERE transcript_id = ?",
                (COMPLETED, now, transcript_id),
            )
        return True

    def fail_rule_task(self, transcript_id):
        with self._write() as conn:
            conn.execute(
                "UPDATE transcripts SET analysis_status = ? WHERE transcript_id = ? AND analysis_status = ?",
                (FAILED, transcript_id, PROCESSING),
            )

    @staticmethod
    def _record_pattern(conn, transcript_id, voice_id, category, expression, count,
                        source, context_dependent, now):
        """Add one transcript's count for one expression to the voice's running totals.

        Does nothing if this transcript already contributed this expression, which makes
        retries and rule/LLM overlap safe.
        """
        if count <= 0:
            return False
        existing = conn.execute(
            "SELECT id, category FROM speaking_patterns WHERE voice_id = ? AND expression = ? ORDER BY id LIMIT 1",
            (voice_id, expression),
        ).fetchone()
        category = existing["category"] if existing else category  # one category per expression

        cur = conn.execute(
            "INSERT OR IGNORE INTO transcript_patterns (transcript_id, expression, category, occurrence_count) "
            "VALUES (?, ?, ?, ?)",
            (transcript_id, expression, category, count),
        )
        if cur.rowcount != 1:
            return False

        if existing:
            conn.execute(
                "UPDATE speaking_patterns SET occurrence_count = occurrence_count + ?, "
                "sample_count = sample_count + 1, last_seen_at = ? WHERE id = ?",
                (count, now, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO speaking_patterns (voice_id, category, expression, source, context_dependent, "
                "occurrence_count, sample_count, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (voice_id, category, expression, source, 1 if context_dependent else 0, count, now, now),
            )
        return True

    # --- LLM batch analysis -------------------------------------------------

    def llm_backlog(self, voice_id, max_attempts=config.STYLE_MAX_ATTEMPTS):
        """Transcripts that passed rule analysis and still need LLM analysis, oldest first."""
        with self._read() as conn:
            rows = conn.execute(
                "SELECT transcript_id, file_path FROM transcripts "
                "WHERE voice_id = ? AND analysis_status = ? AND llm_analysis_status IN (?, ?) AND llm_attempts < ? "
                "ORDER BY created_at, rowid",
                (voice_id, COMPLETED, PENDING, FAILED, max_attempts),
            ).fetchall()
        return [dict(r) for r in rows]

    def claim_llm_batch(self, transcript_ids):
        """Mark transcripts as in LLM analysis. Returns the ids actually claimed."""
        claimed = []
        with self._write() as conn:
            for tid in transcript_ids:
                cur = conn.execute(
                    "UPDATE transcripts SET llm_analysis_status = ?, llm_attempts = llm_attempts + 1 "
                    "WHERE transcript_id = ? AND llm_analysis_status IN (?, ?)",
                    (PROCESSING, tid, PENDING, FAILED),
                )
                if cur.rowcount == 1:
                    claimed.append(tid)
        return claimed

    def complete_llm_batch(self, voice_id, transcript_ids, observations, tone=None, notes=None):
        """Save one LLM batch's results and mark its transcripts done, in one transaction.

        observations: list of (transcript_id, category, expression, count, context_dependent).
        tone: dict of tone votes from this batch; added to the accumulated votes.
        """
        now = utcnow()
        with self._write() as conn:
            placeholders = ",".join("?" * len(transcript_ids))
            valid = {
                r["transcript_id"] for r in conn.execute(
                    f"SELECT transcript_id FROM transcripts WHERE voice_id = ? AND llm_analysis_status = ? "
                    f"AND transcript_id IN ({placeholders})",
                    (voice_id, PROCESSING, *transcript_ids),
                )
            }
            for tid, category, expression, count, context_dependent in observations:
                if tid in valid:
                    self._record_pattern(conn, tid, voice_id, category, expression, count,
                                         "llm", context_dependent, now)

            profile = conn.execute(
                "SELECT tone_profile, speaking_habits FROM voice_profiles WHERE voice_id = ?", (voice_id,)
            ).fetchone()
            tone_profile = json.loads(profile["tone_profile"] or "{}")
            habits = json.loads(profile["speaking_habits"] or "{}")
            if tone:
                tone_profile = merge_tone_votes(tone_profile, tone)
            if notes:
                habits["notes"] = list(notes)[:3]
            conn.execute(
                "UPDATE voice_profiles SET tone_profile = ?, speaking_habits = ?, updated_at = ? WHERE voice_id = ?",
                (json.dumps(tone_profile), json.dumps(habits), now, voice_id),
            )
            conn.executemany(
                "UPDATE transcripts SET llm_analysis_status = ?, llm_processed_at = ? WHERE transcript_id = ?",
                [(COMPLETED, now, tid) for tid in valid],
            )
        return len(valid)

    def fail_llm_batch(self, transcript_ids):
        with self._write() as conn:
            conn.executemany(
                "UPDATE transcripts SET llm_analysis_status = ? WHERE transcript_id = ? AND llm_analysis_status = ?",
                [(FAILED, tid, PROCESSING) for tid in transcript_ids],
            )

    def give_up_llm(self, transcript_ids):
        """Stop retrying LLM analysis for transcripts that can't be analysed (e.g. file missing)."""
        with self._write() as conn:
            conn.executemany(
                "UPDATE transcripts SET llm_analysis_status = ?, llm_attempts = ? WHERE transcript_id = ?",
                [(FAILED, 1_000_000, tid) for tid in transcript_ids],
            )

    # --- recovery after a restart -------------------------------------------

    def reset_interrupted(self):
        """Tasks left 'processing' when the app closed go back to 'pending' so they run again."""
        with self._write() as conn:
            conn.execute("UPDATE transcripts SET analysis_status = ? WHERE analysis_status = ?",
                         (PENDING, PROCESSING))
            conn.execute("UPDATE transcripts SET llm_analysis_status = ? WHERE llm_analysis_status = ?",
                         (PENDING, PROCESSING))

    def pending_rule_ids(self, max_attempts=config.STYLE_MAX_ATTEMPTS):
        with self._read() as conn:
            rows = conn.execute(
                "SELECT transcript_id FROM transcripts WHERE analysis_status IN (?, ?) AND rule_attempts < ? "
                "ORDER BY created_at, rowid",
                (PENDING, FAILED, max_attempts),
            ).fetchall()
        return [r["transcript_id"] for r in rows]

    def voices_with_llm_backlog(self, batch_size, max_attempts=config.STYLE_MAX_ATTEMPTS):
        with self._read() as conn:
            rows = conn.execute(
                "SELECT voice_id FROM transcripts WHERE analysis_status = ? AND llm_analysis_status IN (?, ?) "
                "AND llm_attempts < ? GROUP BY voice_id HAVING COUNT(*) >= ?",
                (COMPLETED, PENDING, FAILED, max_attempts, batch_size),
            ).fetchall()
        return [r["voice_id"] for r in rows]


def merge_tone_votes(existing, new_votes):
    """Add one batch's tone observations to the accumulated vote counts.

    existing: {"formality": {"informal": 3}, "descriptors": {"casual": 2}, ...}
    new_votes: {"formality": "informal", "descriptors": ["casual", "warm"], ...}
    """
    merged = {key: dict(value) for key, value in (existing or {}).items()}
    for key, value in new_votes.items():
        values = value if isinstance(value, list) else [value]
        bucket = merged.setdefault(key, {})
        for v in values:
            bucket[v] = bucket.get(v, 0) + 1
    return merged


# --- shared instance used by the conversation pipeline -----------------------
_default_db = None
_default_lock = threading.Lock()


def get_database():
    """Return the app-wide database, creating it on first use."""
    global _default_db
    with _default_lock:
        if _default_db is None:
            _default_db = StyleDatabase(config.DB_PATH)
        return _default_db


def set_database(db):
    """Swap the app-wide database (used by tests)."""
    global _default_db
    with _default_lock:
        _default_db = db
