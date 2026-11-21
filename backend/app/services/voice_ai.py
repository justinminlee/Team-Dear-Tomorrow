"""AssemblyAI calls for the future-self phone call: speech-to-text, LLM, text-to-speech.

Mirrors VOICE/main.py (verbatim transcription, same LLM Gateway and TTS voices),
but works on in-memory audio so it can run behind a web API.

Settings (backend/.env):
    ASSEMBLYAI_API_KEY    required
    ASSEMBLYAI_VOICE_ID   optional: cloned voice to speak with (defaults to AssemblyAI's aai-jane)
    LLM_GATEWAY_MODEL     optional: any model on AssemblyAI's LLM Gateway
"""
import os
import re
from functools import lru_cache
from pathlib import Path

import assemblyai as aai
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_LLM_MODEL = "qwen3.5-4b-32k-fast"  # same as VOICE/config.py
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com"
MAX_SPOKEN_CHARS = 700


class VoiceAIError(Exception):
    """A speech or LLM provider call failed. The message is safe to show users."""


class NotConfigured(VoiceAIError):
    pass


def _api_key() -> str:
    key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    if not key:
        raise NotConfigured("The AI voice service is not configured (ASSEMBLYAI_API_KEY is missing).")
    return key


@lru_cache(maxsize=1)
def _llm_client(api_key: str) -> httpx.Client:
    # One shared client keeps the connection warm between turns.
    return httpx.Client(
        base_url=LLM_GATEWAY_URL,
        headers={"Authorization": api_key},
        timeout=httpx.Timeout(30, connect=10),
        transport=httpx.HTTPTransport(retries=2),
    )


def _configure_sdk() -> None:
    aai.settings.api_key = _api_key()
    aai.settings.polling_interval = 0.5  # as in VOICE: check transcripts every 0.5s


# ---------- Speech to text ----------

VERBATIM_PROMPT = (
    "Transcribe verbatim, keeping filler words and hesitations such as um, uh, like and you know, "
    "and any profanity."
)


def transcribe(wav: bytes, context: list[str] | None = None) -> str:
    """Transcribe one spoken turn (WAV audio) with AssemblyAI's synchronous API.

    One request, no upload-and-poll, so it takes well under a second for a short
    turn. Like VOICE, it keeps filler words so the same transcripts can feed
    speaking-style learning later. `context` = recent lines of the conversation,
    which helps recognise names and topics.
    """
    _configure_sdk()
    config = aai.SyncTranscriptionConfig(
        language_codes=["en"],
        prompt=VERBATIM_PROMPT,
        conversation_context=context[-4:] if context else None,
    )
    try:
        result = aai.SyncTranscriber(config=config).transcribe(wav)
    except Exception as exc:  # network / API errors
        raise VoiceAIError("Speech recognition is unavailable right now.") from exc
    return (result.text or "").strip()


# ---------- LLM ----------

def chat(messages: list[dict], max_tokens: int = 220, temperature: float = 0.8) -> str:
    model = os.getenv("LLM_GATEWAY_MODEL", "").strip() or DEFAULT_LLM_MODEL
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    try:
        response = _llm_client(_api_key()).post("/v1/chat/completions", json=body)
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
    except NotConfigured:
        raise
    except Exception as exc:
        raise VoiceAIError("Your future self couldn't respond just now.") from exc
    return clean_for_speech(text)


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)
_MARKDOWN = re.compile(r"[*_#`>~]+")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
# *laughs*, (smiles), [pause]: short stage directions an LLM may add, which TTS would read out.
_BOLD = re.compile(r"\*\*|__")
# *laughs* anywhere; (smiles) / [pause] only where a sentence starts, so normal
# brackets mid-sentence ("I was 24 (a while ago)") are kept.
_STAGE_DIRECTION = re.compile(
    r"\*[^*\n]{1,40}\*|(?:^|(?<=[.!?]))\s*(?:\([^)\n]{1,40}\)|\[[^\]\n]{1,40}\])"
)


def clean_for_speech(text: str) -> str:
    """Make an LLM reply safe to read aloud: no reasoning tags, markdown, emojis or stage directions."""
    text = _THINK_BLOCK.sub("", text)
    text = _STAGE_DIRECTION.sub(" ", _BOLD.sub("", text))
    text = _EMOJI.sub("", _MARKDOWN.sub("", text))
    text = re.sub(r"\s+", " ", text).strip().strip('"')
    if len(text) > MAX_SPOKEN_CHARS:
        cut = text[:MAX_SPOKEN_CHARS]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        text = cut[: end + 1] if end > 0 else cut
    return text


# ---------- Text to speech ----------

def synthesize(text: str) -> bytes:
    """Speak text in the configured (cloned) voice. Returns MP3 bytes."""
    _configure_sdk()
    voice_id = os.getenv("ASSEMBLYAI_VOICE_ID", "").strip() or None
    config = aai.TTSConfig(voice_id=voice_id, encoding="mp3")
    try:
        return aai.TextToSpeech().synthesize(text, config).audio
    except Exception as exc:
        raise VoiceAIError("Your future self's voice is unavailable right now.") from exc
