"""Future-self phone call.

POST /call/start  -> the future self's opening line (text + spoken MP3)
POST /call/turn   -> one exchange: the user's recorded audio (WAV) in, the reply (text + MP3) out

The server keeps no call state (it runs serverless), so the browser sends the
conversation so far with each turn. The persona/system prompt is always rebuilt
here from the user's saved questionnaire answers, never taken from the browser.
"""
import base64
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.api.questionnaire import load_active_questions, load_latest_answers
from app.database.session import get_db
from app.services import persona, voice_ai

router = APIRouter(prefix="/call", tags=["call"])

MAX_AUDIO_BYTES = 4 * 1024 * 1024  # under Vercel's 4.5 MB request limit (~2 min of 16 kHz WAV)
MAX_HISTORY = 24                     # most recent messages sent to the model
MAX_MESSAGE_CHARS = 2000


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


HistoryAdapter = TypeAdapter(list[Message])


def load_system_prompt(db: Session, user: dict) -> str:
    """Persona prompt from the user's latest questionnaire answers."""
    questions = load_active_questions(db)
    answers = load_latest_answers(db, uuid.UUID(user["id"]))
    profile = persona.build_profile(user.get("username") or "", questions, answers)
    return persona.build_system_prompt(profile)


def speak(text: str) -> dict:
    audio = voice_ai.synthesize(text)
    return {"text": text, "audio": base64.b64encode(audio).decode("ascii"), "audio_type": "audio/mpeg"}


def provider_error(exc: voice_ai.VoiceAIError) -> HTTPException:
    status = 503 if isinstance(exc, voice_ai.NotConfigured) else 502
    return HTTPException(status, str(exc))


@router.post("/start")
def start_call(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    system = load_system_prompt(db, user)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{persona.CALL_CONNECTED}\n{persona.GREETING_INSTRUCTION}"},
    ]
    try:
        greeting = voice_ai.chat(messages, max_tokens=120)
        if not greeting:
            raise voice_ai.VoiceAIError("Your future self couldn't respond just now.")
        return {"reply": speak(greeting)}
    except voice_ai.VoiceAIError as exc:
        raise provider_error(exc) from exc


@router.post("/turn")
async def call_turn(
    audio: UploadFile = File(...),
    history: str = Form("[]"),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        past = HistoryAdapter.validate_python(json.loads(history))
    except (ValueError, ValidationError):
        raise HTTPException(422, "Invalid conversation history") from None

    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "That recording is too long. Try a shorter answer.")
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise HTTPException(415, "Recording must be WAV audio")

    # The provider calls block, so run them off the event loop.
    try:
        context = [m.content for m in past[-4:]]
        heard = await run_in_threadpool(voice_ai.transcribe, data, context)
        if not heard:
            # Nothing intelligible: let the browser keep listening, no reply.
            return {"heard": "", "reply": None}

        system = await run_in_threadpool(load_system_prompt, db, user)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": persona.CALL_CONNECTED},
            *({"role": m.role, "content": m.content} for m in past[-MAX_HISTORY:]),
            {"role": "user", "content": heard[:MAX_MESSAGE_CHARS]},
        ]
        reply = await run_in_threadpool(voice_ai.chat, messages)
        if not reply:
            raise voice_ai.VoiceAIError("Your future self couldn't respond just now.")
        return {"heard": heard, "reply": await run_in_threadpool(speak, reply)}
    except voice_ai.VoiceAIError as exc:
        raise provider_error(exc) from exc
