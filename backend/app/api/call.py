"""Future-self phone call.

GET  /call/voices -> the cloned voices the future self can speak with (TJ, Peter, Lucas)
POST /call/start  -> the future self's opening line (text + spoken MP3)
POST /call/turn   -> one exchange: the user's recorded audio (WAV) in, the reply (text + MP3) out

Both POSTs take an optional `voice` (a name from /call/voices); the browser sends the
same one every turn.

The server keeps no call state (it runs serverless), so the browser sends the
conversation so far with each turn. The persona/system prompt is always rebuilt
here from the user's saved questionnaire answers, never taken from the browser.

Speaking style: the prompt also gets the habits learned from the user's own speech
(style_service.style_notes_for), and what the user says on the call keeps teaching
it, for users who agreed to style learning in the questionnaire.
"""
import base64
import json
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.api.questionnaire import load_active_questions, load_latest_answers
from app.database.session import get_db
from app.services import persona, scripted_replies, style_service, voice_ai
from app.services.style_store import StyleStore

router = APIRouter(prefix="/call", tags=["call"])

MAX_AUDIO_BYTES = 4 * 1024 * 1024  # under Vercel's 4.5 MB request limit (~2 min of 16 kHz WAV)
MAX_HISTORY = 24                     # most recent messages sent to the model
MAX_MESSAGE_CHARS = 2000


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


HistoryAdapter = TypeAdapter(list[Message])


def load_system_prompt(db: Session, user: dict, store: StyleStore | None = None) -> str:
    """Persona prompt from the user's latest questionnaire answers and learned speaking style."""
    questions = load_active_questions(db)
    answers = load_latest_answers(db, uuid.UUID(user["id"]))
    profile = persona.build_profile(user.get("username") or "", questions, answers)
    style_notes = style_service.style_notes_for(store, user["id"]) if store else None
    prompt = persona.build_system_prompt(profile, style_notes)
    scripted = scripted_replies.scripted_section(profile.restricted_topics)
    return f"{prompt}\n\n{scripted}" if scripted else prompt


class StartRequest(BaseModel):
    voice: str | None = Field(default=None, max_length=40)


def check_voice(voice: str | None) -> str | None:
    """422 for a voice name that isn't configured, before any paid API call."""
    voice = (voice or "").strip() or None
    if voice and voice not in voice_ai.available_voices():
        raise HTTPException(422, f"Unknown voice. Choose one of: {', '.join(voice_ai.available_voices())}")
    return voice


def speak(text: str, voice: str | None = None) -> dict:
    audio = voice_ai.synthesize(text, voice)
    return {"text": text, "audio": base64.b64encode(audio).decode("ascii"), "audio_type": "audio/mpeg"}


def provider_error(exc: voice_ai.VoiceAIError) -> HTTPException:
    status = 503 if isinstance(exc, voice_ai.NotConfigured) else 502
    return HTTPException(status, str(exc))


@router.get("/voices")
def list_voices():
    voices = voice_ai.available_voices()
    return {"voices": voices, "default": voices[0] if voices else None}


@router.post("/start")
def start_call(
    background: BackgroundTasks,
    body: StartRequest | None = None,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
    store: StyleStore = Depends(style_service.get_style_store),
):
    voice = check_voice(body.voice if body else None)
    system = load_system_prompt(db, user, store)
    # Analyse any samples still waiting (e.g. if an earlier background run was cut short).
    background.add_task(style_service.learn_style, store, user["id"])
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{persona.CALL_CONNECTED}\n{persona.GREETING_INSTRUCTION}"},
    ]
    try:
        greeting = voice_ai.chat(messages, max_tokens=120)
        if not greeting:
            raise voice_ai.VoiceAIError("Your future self couldn't respond just now.")
        return {"reply": speak(greeting, voice)}
    except voice_ai.VoiceAIError as exc:
        raise provider_error(exc) from exc


@router.post("/turn")
async def call_turn(
    background: BackgroundTasks,
    audio: UploadFile = File(...),
    history: str = Form("[]"),
    voice: str | None = Form(None),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
    store: StyleStore = Depends(style_service.get_style_store),
):
    try:
        past = HistoryAdapter.validate_python(json.loads(history))
    except (ValueError, ValidationError):
        raise HTTPException(422, "Invalid conversation history") from None
    voice = check_voice(voice)

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

        # What the user said teaches their speaking style (only if they agreed to learning).
        if await run_in_threadpool(style_service.record_call_turn, store, user["id"], heard):
            background.add_task(style_service.learn_style, store, user["id"])

        system = await run_in_threadpool(load_system_prompt, db, user, store)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": persona.CALL_CONNECTED},
            *({"role": m.role, "content": m.content} for m in past[-MAX_HISTORY:]),
            {"role": "user", "content": heard[:MAX_MESSAGE_CHARS]},
        ]
        reply = await run_in_threadpool(voice_ai.chat, messages)
        if not reply:
            raise voice_ai.VoiceAIError("Your future self couldn't respond just now.")
        return {"heard": heard, "reply": await run_in_threadpool(speak, reply, voice)}
    except voice_ai.VoiceAIError as exc:
        raise provider_error(exc) from exc
