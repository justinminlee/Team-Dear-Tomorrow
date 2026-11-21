"""Merge newly found speaking habits into a user's long-term style profile.

Port of VOICE/style_learner.py. Runs in a FastAPI background task after the response
is sent, so learning never slows down a reply.
"""
from __future__ import annotations

import logging
from typing import Callable

from app.services import style_analyzer
from app.services.style_store import MAX_ATTEMPTS, StyleStore

log = logging.getLogger(__name__)

# Run the LLM analysis once this many analysed transcripts are waiting (1 = every recording).
LLM_ANALYSIS_BATCH_SIZE = 1


def frequency_per_100_words(occurrence_count: int, total_words: int) -> float:
    """How often a habit appears per 100 words the user has spoken."""
    if total_words <= 0:
        return 0.0
    return occurrence_count / total_words * 100


class StyleLearner:
    """Rule analysis per transcript, then LLM analysis in batches. All counts are additive."""

    def __init__(self, store: StyleStore, chat_fn: Callable[..., str],
                 batch_size: int = LLM_ANALYSIS_BATCH_SIZE, max_attempts: int = MAX_ATTEMPTS,
                 vocabulary: dict | None = None):
        self.store = store
        self.chat_fn = chat_fn
        self.batch_size = max(1, batch_size)
        self.max_attempts = max_attempts
        self.vocabulary = vocabulary or style_analyzer.load_vocabulary()

    def process_voice(self, voice_id: str) -> int:
        """Analyse every waiting transcript of one key (including earlier failures). Never raises."""
        done = 0
        try:
            for transcript_id in self.store.pending_rule_ids(voice_id, self.max_attempts):
                done += self._rule_analysis(transcript_id)
            self.run_llm_batches(voice_id)
        except Exception:
            log.exception("Style learning failed for %s", voice_id)
        return done

    def _rule_analysis(self, transcript_id: str) -> bool:
        row = self.store.claim_rule_task(transcript_id, self.max_attempts)
        if row is None:
            return False  # already done, being processed, or out of retries
        try:
            learned = self.store.learned_vocabulary(row["voice_id"])
            found = style_analyzer.extract_rule_patterns(row["text"], self.vocabulary, learned)
            observations = [
                (category, expression, count, "rule", False)
                for category, expressions in found.items()
                for expression, count in expressions.items()
            ]
            self.store.complete_rule_task(transcript_id, observations)
            log.info("Rule analysis done for transcript %s (%d habits)", transcript_id, len(observations))
            return True
        except Exception:
            log.exception("Rule analysis failed for transcript %s", transcript_id)
            self.store.fail_rule_task(transcript_id)
            return False

    def run_llm_batches(self, voice_id: str) -> int:
        """Run LLM analysis for every full batch of waiting transcripts."""
        completed = 0
        while True:
            backlog = self.store.llm_backlog(voice_id, self.max_attempts)
            if len(backlog) < self.batch_size:
                return completed
            if not self._run_one_batch(voice_id, backlog[: self.batch_size]):
                return completed  # leave the rest for next time instead of hammering a failing API
            completed += 1

    def _run_one_batch(self, voice_id: str, rows: list[dict]) -> bool:
        claimed = set(self.store.claim_llm_batch([r["transcript_id"] for r in rows]))
        rows = [r for r in rows if r["transcript_id"] in claimed]
        if not rows:
            return False

        labelled, label_to_id = [], {}
        for i, row in enumerate(rows, start=1):
            labelled.append((f"T{i}", row["text"]))
            label_to_id[f"T{i}"] = row["transcript_id"]

        try:
            result = style_analyzer.analyze_with_llm(labelled, self.chat_fn, self.vocabulary)
            observations = [
                (label_to_id[label], category, expression, count, context_dependent)
                for label, category, expression, count, context_dependent in result["observations"]
            ]
            self.store.complete_llm_batch(voice_id, list(label_to_id.values()), observations,
                                          result["tone"], result["notes"])
            log.info("LLM analysis done for %d transcripts of %s", len(label_to_id), voice_id)
            return True
        except Exception:
            # Nothing was saved (one transaction), so a retry can't inflate counts.
            log.exception("LLM analysis failed; batch will be retried later")
            self.store.fail_llm_batch(list(label_to_id.values()))
            return False
