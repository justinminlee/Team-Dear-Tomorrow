"""Speaking-style learning for the website, glued to the call and the questionnaire.

- Questionnaire: POST /questionnaire/voice-samples queues spoken answers in
  public.fact_transcript; `learn_style` (a background task) then analyses them here,
  so a website user doesn't need the VOICE app for their style to be learned.
- Call: `style_notes_for` adds the learned habits to the future self's system prompt,
  and `record_call_turn` keeps learning from what the user says on the call, but only
  for users who agreed to style learning (learning_enabled = 1).

Analysis uses the same tables, status values and rules as the VOICE app, and every
task is claimed with a conditional UPDATE, so both can run without double counting.
"""
from __future__ import annotations

import logging
import os
import uuid

from app.database.session import engine
from app.services import style_prompt, voice_ai
from app.services.style_analyzer import word_count
from app.services.style_learner import StyleLearner
from app.services.style_store import StyleStore, user_style_key

log = logging.getLogger(__name__)


def get_style_store() -> StyleStore:
    """FastAPI dependency (tests replace it with an in-memory store)."""
    return StyleStore(engine)


def analysis_chat(messages: list[dict], max_tokens: int = 900, temperature: float | None = 0.2) -> str:
    """LLM call for style analysis. Unlike voice_ai.chat it returns the raw reply,
    because the analyzer needs the JSON intact (voice_ai.chat strips symbols and
    shortens text for speech)."""
    model = os.getenv("LLM_GATEWAY_MODEL", "").strip() or voice_ai.DEFAULT_LLM_MODEL
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    response = voice_ai._llm_client(voice_ai._api_key()).post("/v1/chat/completions", json=body)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def learn_style(store: StyleStore, user_id: str) -> None:
    """Background task: analyse every waiting sample of this user. Never raises."""
    StyleLearner(store, analysis_chat).process_voice(user_style_key(user_id))


def style_notes_for(store: StyleStore, user_id: str) -> str | None:
    """Learned style text for the call prompt, or None. A DB problem never breaks the call."""
    try:
        return style_prompt.style_notes(store.get_style_profile(user_style_key(user_id)))
    except Exception:
        log.exception("Could not load the speaking style profile; calling without it")
        return None


def record_call_turn(store: StyleStore, user_id: str, heard: str) -> bool:
    """Queue what the user said on the call as a style sample, if they agreed to learning.

    Returns True if it was queued (then run learn_style in the background).
    """
    try:
        profile = store.get_style_profile(user_style_key(user_id))
        if not profile or profile.get("learning_enabled") != 1:
            return False
        text = " ".join(heard.split())
        return store.register_transcript(f"c{uuid.uuid4().hex}", user_style_key(user_id), text, word_count(text))
    except Exception:
        log.exception("Could not queue a call turn for style learning")
        return False
