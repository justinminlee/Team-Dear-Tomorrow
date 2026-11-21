"""Spoken questionnaire answers.

Some questions (the free-text ones in "Your Future Self") are answered out loud:

1. POST /questionnaire/transcribe
   The browser uploads the recording; it is turned into text with AssemblyAI and the
   text is shown as the answer. Same settings as the voice app (VOICE/main.py):
   disfluencies on, no profanity filter, unformatted text, so "um", "like" and
   swearing are kept. The audio is never stored, and AssemblyAI's copy is deleted.

2. POST /questionnaire/voice-samples
   After the answers are saved (POST /questionnaire/answers), the page sends which of
   them were spoken. They are queued as speaking-style samples in the voice app's
   tables (dim_voice_style / fact_transcript). The voice app analyses them the next time
   it starts, so the future self talks a bit like the user from the first conversation.

Speaking style is stored per user, keyed by the user's id. Recording an answer counts
as agreeing to style learning, which the questionnaire page explains next to the button.
"""
import asyncio
import hashlib
import logging
import os
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.api.questionnaire import load_latest_answers
from app.database.session import get_db

log = logging.getLogger(__name__)
router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])

ASSEMBLYAI_URL = "https://api.assemblyai.com/v2"
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # several minutes of compressed browser audio
MIN_AUDIO_BYTES = 1000              # anything smaller is an empty recording
TRANSCRIBE_TIMEOUT_SECONDS = 90
POLL_SECONDS = 1.0

# Same definition of a word as the voice app's analyzer (VOICE/style_analyzer.py).
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")


def word_count(value: str) -> int:
    return len(_WORD_RE.findall(value or ""))


def sample_id(user_id: str, question_id: uuid.UUID, spoken: str) -> str:
    """Same user + question + words always gives the same id, so a sample is stored once."""
    return "q" + hashlib.sha256(f"{user_id}:{question_id}:{spoken}".encode()).hexdigest()[:31]


# ---------- 1. Recording -> text ----------

def assemblyai_key() -> str:
    key = os.getenv("ASSEMBLYAI_API_KEY", "")
    if not key:
        raise HTTPException(503, "Voice answers are not set up on the server (ASSEMBLYAI_API_KEY).")
    return key


async def transcribe_audio(audio: bytes, client: httpx.AsyncClient | None = None) -> str:
    """Upload audio to AssemblyAI, wait for the transcript and return its text."""
    headers = {"authorization": assemblyai_key()}
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    transcript_id = None
    try:
        upload = await client.post(f"{ASSEMBLYAI_URL}/upload", headers=headers, content=audio)
        upload.raise_for_status()
        created = await client.post(f"{ASSEMBLYAI_URL}/transcript", headers=headers, json={
            "audio_url": upload.json()["upload_url"],
            "speech_models": ["universal-2"],
            "language_code": "en",
            "disfluencies": True,
            "filter_profanity": False,
            "format_text": False,
        })
        created.raise_for_status()
        transcript_id = created.json()["id"]

        loop = asyncio.get_running_loop()
        deadline = loop.time() + TRANSCRIBE_TIMEOUT_SECONDS
        while True:
            result = await client.get(f"{ASSEMBLYAI_URL}/transcript/{transcript_id}", headers=headers)
            result.raise_for_status()
            data = result.json()
            if data["status"] == "completed":
                return " ".join((data.get("text") or "").split())
            if data["status"] == "error":
                log.warning("AssemblyAI could not transcribe an answer: %s", data.get("error"))
                raise HTTPException(422, "Couldn't understand that recording. Please try again.")
            if loop.time() > deadline:
                raise HTTPException(504, "Transcription took too long. Please try again.")
            await asyncio.sleep(POLL_SECONDS)
    except httpx.HTTPError:
        log.exception("AssemblyAI request failed")
        raise HTTPException(502, "The transcription service is unavailable. Please try again.") from None
    finally:
        if transcript_id:
            try:  # we keep only the saved answer, not AssemblyAI's copy of the audio and text
                await client.delete(f"{ASSEMBLYAI_URL}/transcript/{transcript_id}", headers=headers)
            except httpx.HTTPError:
                log.warning("Could not delete transcript %s from AssemblyAI", transcript_id)
        if own_client:
            await client.aclose()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), user: dict = Depends(current_user)):
    """Turn one recorded answer into text. Nothing is saved here."""
    content_type = (audio.content_type or "").split(";")[0]
    if not content_type.startswith(("audio/", "video/webm")):
        raise HTTPException(415, "Please upload an audio recording.")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "That recording is too long. Please keep it to a few minutes.")
    if len(data) < MIN_AUDIO_BYTES:
        raise HTTPException(422, "The recording was empty. Please try again.")
    spoken = await transcribe_audio(data)
    if not spoken:
        raise HTTPException(422, "I didn't hear anything. Please try again.")
    return {"text": spoken}


# ---------- 2. Saved spoken answers -> style samples ----------

class VoiceSamplesRequest(BaseModel):
    # Ids of questions whose saved answer was spoken, not typed.
    question_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


def store_samples(db: Session, user: dict, samples: list[tuple[uuid.UUID, str]]) -> int:
    """Insert style samples for the voice app. Returns how many were new."""
    key = str(user["id"])
    db.execute(text(
        "INSERT INTO public.dim_voice_style (voice_id, display_name, learning_enabled, created_at, updated_at) "
        "VALUES (:key, :name, 1, now(), now()) "
        "ON CONFLICT (voice_id) DO UPDATE SET learning_enabled = 1, updated_at = now()"
    ), {"key": key, "name": user.get("username") or None})
    added = 0
    for question_id, spoken in samples:
        result = db.execute(text(
            "INSERT INTO public.fact_transcript (transcript_id, voice_id, text, word_count, created_at) "
            "VALUES (:tid, :key, :text, :words, clock_timestamp()) ON CONFLICT (transcript_id) DO NOTHING"
        ), {"tid": sample_id(key, question_id, spoken), "key": key, "text": spoken, "words": word_count(spoken)})
        added += result.rowcount
    db.commit()
    return added


@router.post("/voice-samples")
def save_voice_samples(body: VoiceSamplesRequest, user: dict = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Queue the user's saved spoken answers for speaking-style learning.

    Only answers that are already saved are used, so the text always matches what is
    stored in fact_profile_answer. Sending the same answers again adds nothing.
    """
    latest = load_latest_answers(db, uuid.UUID(str(user["id"])))
    samples = [(qid, latest[qid].strip()) for qid in dict.fromkeys(body.question_ids)
               if isinstance(latest.get(qid), str) and latest[qid].strip()]
    if not samples:
        return {"queued": 0}
    try:
        return {"queued": store_samples(db, user, samples)}
    except Exception:
        db.rollback()
        log.exception("Could not queue spoken answers for style learning")
        raise HTTPException(503, "Your answers are saved, but voice learning is unavailable right now.") from None
