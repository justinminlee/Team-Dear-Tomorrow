"""Dear Tomorrow: a voice chat with your future self.

Usage:
    uv run main.py                 normal conversation (asks once per voice before learning)
    uv run main.py --no-learning   talk without saving anything for style learning
    uv run main.py --reset-style   delete everything learned for one voice
"""
import argparse
import logging
import wave

import assemblyai as aai
import httpx
import sounddevice as sd

import config
from config import API_KEY, MODEL, VOICES
from database import close_database, get_database
from prompts import BASE_SYSTEM_PROMPT, build_system_prompt
from style_worker import create_style_service
from transcript import delete_voice_transcripts

log = logging.getLogger(__name__)


# --- Voice selection ------------------------------------------------------------

def select_voice():
    """Let the user pick one of the cloned voices and return its Voice ID."""
    names = list(VOICES.keys())

    print("\nSelect your voice:")
    for i, name in enumerate(names, start=1):
        print(f"{i}. {name}")

    while True:
        choice = input("Select a number: ")
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return VOICES[names[int(choice) - 1]]
        print("Invalid choice. Please try again.")


def voice_name(voice_id):
    """Return the display name for a Voice ID (e.g. "TJ"), or the ID itself if unknown."""
    for name, vid in VOICES.items():
        if vid == voice_id:
            return name
    return voice_id


# --- Speech to text ---------------------------------------------------------------

def listen():
    """Record from the mic until Enter is pressed, then transcribe it with AssemblyAI."""
    frames = []
    input("\nPress Enter and start talking...")

    with sd.RawInputStream(
        samplerate=16000,
        channels=1,
        dtype="int16",
        callback=lambda data, *_: frames.append(bytes(data))
    ):
        input("Listening... press Enter when you're done.")

    # Save as a WAV file.
    with wave.open("you.wav", "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"".join(frames))

    # Preserve filler words, profanity, and natural speech patterns.
    transcription_config = aai.TranscriptionConfig(
        speech_models=["universal-2"],
        language_code="en",
        disfluencies=True,
        filter_profanity=False,
        format_text=False
    )

    transcript = aai.Transcriber(config=transcription_config).transcribe("you.wav")
    if transcript.error:
        raise RuntimeError(transcript.error)

    return transcript.text or ""


# --- LLM ----------------------------------------------------------------------------

messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT}]

# One shared client keeps the connection open between turns (no new TLS handshake each time),
# and retries the connection up to 3 times if the network drops for a moment.
# httpx.Client is thread-safe, so the background style worker shares it too.
llm_client = httpx.Client(
    base_url="https://llm-gateway.assemblyai.com",
    headers={"Authorization": API_KEY},
    timeout=httpx.Timeout(30, connect=10),
    transport=httpx.HTTPTransport(retries=3),
)


def chat(chat_messages, max_tokens=200, temperature=None):
    """Send messages to the LLM Gateway and return the reply text."""
    body = {"model": MODEL, "messages": chat_messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    response = llm_client.post("/v1/chat/completions", json=body)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def personalised_system_prompt(voice_id):
    """System prompt with the latest saved speaking style. Falls back to the default on any error."""
    if not voice_id:
        return BASE_SYSTEM_PROMPT
    try:
        return build_system_prompt(get_database().get_style_profile(voice_id))
    except Exception:
        log.exception("Could not load speaking style profile; using the default prompt")
        return BASE_SYSTEM_PROMPT


def think(user_text, voice_id=None):
    """Reply to the user, speaking in their learned style when one exists.

    The system message is refreshed every turn so newly learned habits apply right away,
    while the rest of the conversation history is kept.
    """
    messages[0] = {"role": "system", "content": personalised_system_prompt(voice_id)}
    user_message = {"role": "user", "content": user_text}

    reply = chat(messages + [user_message])

    # Only keep the turn in history once the reply has arrived.
    messages.extend([user_message, {"role": "assistant", "content": reply}])
    return reply


# --- Text to speech -------------------------------------------------------------

def speak(text, voice_id):
    """Read text out loud in the selected cloned voice, playing audio as it streams in."""
    tts_config = aai.TTSConfig(voice_id=voice_id)

    with aai.TTSSession(tts_config, api_key=API_KEY) as session:
        with sd.RawOutputStream(samplerate=24000, channels=1, dtype="int16") as speaker:
            for chunk in session.speak(text):
                speaker.write(chunk)


# --- Speaking style learning setup ------------------------------------------------

YES = {"y", "yes"}
NO = {"n", "no"}


def ask_learning_consent(db, voice_id, ask_again=False):
    """Ask once per voice whether we may learn from their speech. The answer is remembered.

    ask_again=True (the --learn option) asks again even if the user said no before.
    """
    consent = db.get_learning_consent(voice_id)
    if consent is not None and not ask_again:
        if not consent:
            print("(Speaking style learning is OFF for this voice. To turn it on: uv run main.py --learn)")
        return consent

    where = "your Supabase database" if config.STYLE_DB == "supabase" else "a database on this computer"
    print("\nDear Tomorrow can learn how you talk (filler words, slang, favourite phrases)")
    print("so your future self sounds more like you. Your words are saved as text files on this")
    print(f"computer, and the habits found in them are saved to {where}.")
    print("You can delete them anytime with: uv run main.py --reset-style")
    answer = ""
    while answer not in YES | NO:  # a blank Enter or a typo must not silently mean "no"
        answer = input("Allow speaking style learning for this voice? (y/n): ").strip().lower()
    consent = answer in YES
    db.set_learning_consent(voice_id, consent)
    print("(Learning is ON.)" if consent else "(Learning is OFF. To turn it on later: uv run main.py --learn)")
    return consent


def start_style_learning(voice_id, no_learning, ask_again=False):
    """Return (style_service, learning_on). If anything fails, the chat just runs without learning."""
    if not config.STYLE_LEARNING_ENABLED or no_learning:
        return None, False
    try:
        db = get_database()
        db.ensure_profile(voice_id, voice_name(voice_id))
        learning = ask_learning_consent(db, voice_id, ask_again)
        service = create_style_service(db, chat)
        service.start()  # also resumes analysis left unfinished last time
        return service, learning
    except Exception as e:
        log.exception("Style learning could not start")
        print(f"(Speaking style learning is off this session: {type(e).__name__})")
        return None, False


def reset_style():
    """Delete everything learned for one voice: DB rows and transcript file."""
    voice_id = select_voice()
    name = voice_name(voice_id)
    answer = input(f"Delete all learned speaking style data for {name}? Type 'yes' to confirm: ")
    if answer.strip().lower() != "yes":
        print("Cancelled.")
        return
    removed = get_database().reset_profile(voice_id)
    delete_voice_transcripts(voice_id, config.TRANSCRIPTS_DIR)
    print(f"Deleted the speaking style profile for {name} ({removed} transcripts).")


# --- Main ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Dear Tomorrow voice chat")
    parser.add_argument("--no-learning", action="store_true",
                        help="don't save or analyse anything this session")
    parser.add_argument("--learn", action="store_true",
                        help="ask the learning question again (e.g. to turn learning back on)")
    parser.add_argument("--reset-style", action="store_true",
                        help="delete the learned speaking style and transcripts for one voice")
    return parser.parse_args()


def setup_logging():
    # Log to a file so background messages don't interrupt the conversation on screen.
    # Only IDs and counts are logged, never what the user said.
    logging.basicConfig(
        filename=config.LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main():
    args = parse_args()
    setup_logging()

    if args.reset_style:
        reset_style()
        return

    # Select a cloned voice before starting the conversation.
    voice_id = select_voice()
    style_service, learning = start_style_learning(voice_id, args.no_learning, args.learn)

    print("Dear Tomorrow is ready. Say 'goodbye' to exit.")

    try:
        while True:
            # A network hiccup in any step shouldn't end the conversation.
            try:
                user_text = listen().strip()

                if not user_text:
                    print("(Didn't catch that, try again.)")
                    continue

                print(f"You: {user_text}")

                # Save the user's words and queue them for background analysis.
                # This returns immediately; the reply below never waits for it.
                if learning:
                    style_service.record(user_text, voice_id)

                if "goodbye" in user_text.lower():
                    speak("Take care of yourself. See you in the future!", voice_id)
                    break

                reply = think(user_text, voice_id)
                print(f"Dear Tomorrow: {reply}")
                speak(reply, voice_id)

            except Exception as e:
                print(f"(Connection problem: {type(e).__name__}: {e}. Please say that again.)")
    finally:
        if style_service:
            if style_service.worker.pending_count():
                print("(Saving what I learned about how you talk...)")
            style_service.shutdown()
        close_database()


if __name__ == "__main__":
    main()
