"""Merge newly found speaking habits into a voice's long-term style profile."""
import logging

import config
import style_analyzer
from transcript import read_transcript

log = logging.getLogger(__name__)


def frequency_per_100_words(occurrence_count, total_words):
    """Normalised frequency: how often a habit appears per 100 words the user has spoken."""
    if total_words <= 0:
        return 0.0
    return occurrence_count / total_words * 100


class StyleLearner:
    """Runs analysis for single transcripts and LLM batches, and saves the merged results.

    All counting is additive: new observations are added to the stored totals, so one
    new transcript can never overwrite what was learned before.
    """

    def __init__(self, db, chat_fn, transcripts_dir=config.TRANSCRIPTS_DIR,
                 batch_size=config.LLM_ANALYSIS_BATCH_SIZE,
                 max_attempts=config.STYLE_MAX_ATTEMPTS, vocabulary=None):
        self.db = db
        self.chat_fn = chat_fn
        self.transcripts_dir = transcripts_dir
        self.batch_size = max(1, batch_size)
        self.max_attempts = max_attempts
        self.vocabulary = vocabulary or style_analyzer.load_vocabulary()

    def process_transcript(self, transcript_id):
        """Rule-based analysis for one transcript, then an LLM batch if enough have piled up."""
        row = self.db.claim_rule_task(transcript_id, self.max_attempts)
        if row is None:
            return False  # already done, being processed, or out of retries

        voice_id = row["voice_id"]
        try:
            text = read_transcript(row["file_path"], self.transcripts_dir, transcript_id)
            learned = self.db.learned_vocabulary(voice_id)
            found = style_analyzer.extract_rule_patterns(text, self.vocabulary, learned)
            observations = [
                (category, expression, count, "rule", False)
                for category, expressions in found.items()
                for expression, count in expressions.items()
            ]
            self.db.complete_rule_task(transcript_id, observations)
            log.info("Rule analysis done for transcript %s (%d habits found)", transcript_id, len(observations))
        except Exception:
            log.exception("Rule analysis failed for transcript %s", transcript_id)
            self.db.fail_rule_task(transcript_id)
            return False

        self.run_llm_batches(voice_id)
        return True

    def run_llm_batches(self, voice_id):
        """Run LLM analysis for every full batch of waiting transcripts. Returns batches completed."""
        completed = 0
        while True:
            backlog = self.db.llm_backlog(voice_id, self.max_attempts)
            if len(backlog) < self.batch_size:
                return completed
            if not self._run_one_batch(voice_id, backlog[:self.batch_size]):
                return completed  # leave the rest for the next trigger instead of hammering a failing API
            completed += 1

    def _run_one_batch(self, voice_id, rows):
        claimed = set(self.db.claim_llm_batch([r["transcript_id"] for r in rows]))
        rows = [r for r in rows if r["transcript_id"] in claimed]
        if not rows:
            return False

        labelled, label_to_id, unreadable = [], {}, []
        for i, row in enumerate(rows, start=1):
            try:
                text = read_transcript(row["file_path"], self.transcripts_dir, row["transcript_id"])
            except (OSError, ValueError, LookupError):
                unreadable.append(row["transcript_id"])
                continue
            label = f"T{i}"
            labelled.append((label, text))
            label_to_id[label] = row["transcript_id"]
        if unreadable:
            log.warning("Skipping %d unreadable transcripts in LLM batch", len(unreadable))
            self.db.give_up_llm(unreadable)
        if not labelled:
            return False

        try:
            result = style_analyzer.analyze_with_llm(labelled, self.chat_fn, self.vocabulary)
            observations = [
                (label_to_id[label], category, expression, count, context_dependent)
                for label, category, expression, count, context_dependent in result["observations"]
            ]
            self.db.complete_llm_batch(voice_id, list(label_to_id.values()), observations,
                                       result["tone"], result["notes"])
            log.info("LLM analysis done for %d transcripts of voice %s", len(label_to_id), voice_id)
            return True
        except Exception:
            # Nothing was saved (the DB update is one transaction), so a retry can't inflate counts.
            log.exception("LLM analysis failed; batch will be retried later")
            self.db.fail_llm_batch(list(label_to_id.values()))
            return False
