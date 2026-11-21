"""Background worker that learns speaking style without slowing the conversation down.

The conversation loop only saves the transcript and drops a task on a queue, which takes
a few milliseconds. One long-lived background thread does the actual analysis.

Every task is recorded in the database before it is queued, so nothing is lost if the
queue is full or the app closes: unfinished tasks are picked up again on the next start.
"""
import logging
import queue
import threading

import config
from database import get_database
from style_analyzer import word_count
from style_learner import StyleLearner
from transcript import save_transcript

log = logging.getLogger(__name__)

_STOP = object()


class StyleWorker:
    """A single background thread that processes analysis tasks one at a time."""

    def __init__(self, learner, maxsize=config.STYLE_QUEUE_SIZE):
        self.learner = learner
        self._queue = queue.Queue(maxsize=maxsize)
        self._thread = threading.Thread(target=self._run, name="style-worker", daemon=True)
        self._started = False

    def start(self):
        if not self._started:
            self._thread.start()
            self._started = True

    def submit(self, transcript_id):
        """Queue rule analysis for a transcript. Never blocks. Returns False if the queue is full."""
        return self._put(("transcript", transcript_id))

    def submit_llm_check(self, voice_id):
        """Queue a check for waiting LLM batches of one voice."""
        return self._put(("llm", voice_id))

    def _put(self, task):
        try:
            self._queue.put_nowait(task)
            return True
        except queue.Full:
            # The task is already "pending" in the DB, so it will be recovered on the next start.
            log.warning("Style queue is full; task %s stays pending for later", task[0])
            return False

    def pending_count(self):
        return self._queue.qsize()

    def wait_until_idle(self, timeout=None):
        """Block until every queued task is finished (used by tests and shutdown)."""
        done = threading.Event()

        def waiter():
            self._queue.join()
            done.set()

        threading.Thread(target=waiter, daemon=True).start()
        return done.wait(timeout)

    def _run(self):
        while True:
            task = self._queue.get()
            try:
                if task is _STOP:
                    return
                kind, value = task
                if kind == "transcript":
                    self.learner.process_transcript(value)
                elif kind == "llm":
                    self.learner.run_llm_batches(value)
            except Exception:
                # A failing task must never kill the worker or the conversation.
                log.exception("Style task failed")
            finally:
                self._queue.task_done()

    def shutdown(self, timeout=config.STYLE_SHUTDOWN_TIMEOUT):
        """Let queued tasks finish (up to timeout), then stop the thread.

        Anything not finished in time is still marked pending/processing in the DB and is
        resumed on the next start, so no task is silently lost.
        """
        if not self._started:
            return True
        try:
            self._queue.put(_STOP, timeout=timeout)
        except queue.Full:
            return False
        self._thread.join(timeout)
        return not self._thread.is_alive()


class StyleLearningService:
    """What the conversation loop talks to: record a transcript, start, recover and stop."""

    def __init__(self, db, learner, worker, transcripts_dir=config.TRANSCRIPTS_DIR):
        self.db = db
        self.learner = learner
        self.worker = worker
        self.transcripts_dir = transcripts_dir

    def start(self):
        """Start the worker and resume any tasks left over from a previous run."""
        self.worker.start()
        self.recover()

    def recover(self):
        try:
            self.db.reset_interrupted()
            for transcript_id in self.db.pending_rule_ids(self.learner.max_attempts):
                self.worker.submit(transcript_id)
            for voice_id in self.db.voices_with_llm_backlog(self.learner.batch_size, self.learner.max_attempts):
                self.worker.submit_llm_check(voice_id)
        except Exception:
            log.exception("Could not recover pending style tasks")

    def record(self, text, voice_id):
        """Save the user's words and queue them for analysis. Returns the transcript id, or None.

        This never raises: a problem here must not interrupt the conversation.
        """
        text = (text or "").strip()
        if not text:
            return None
        try:
            # A local copy goes to transcripts/<voice>.txt; the database keeps the text itself,
            # so analysis never depends on a path that only exists on this computer.
            transcript_id, _ = save_transcript(text, voice_id, self.transcripts_dir)
            text = " ".join(text.split())  # same clean-up as the local copy
            self.db.register_transcript(transcript_id, voice_id, text, word_count(text))
            self.worker.submit(transcript_id)
            return transcript_id
        except Exception:
            log.exception("Could not record transcript for style learning")
            return None

    def shutdown(self, timeout=config.STYLE_SHUTDOWN_TIMEOUT):
        return self.worker.shutdown(timeout)


def create_style_service(db, chat_fn):
    """Build the service. chat_fn(messages, max_tokens=..., temperature=...) returns the LLM reply text."""
    db = db or get_database()
    learner = StyleLearner(db, chat_fn)
    return StyleLearningService(db, learner, StyleWorker(learner))
