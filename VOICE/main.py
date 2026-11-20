import os
import wave

import assemblyai as aai
import httpx
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["ASSEMBLYAI_API_KEY"]

# Store available cloned voices
VOICES = {
    "TJ": os.environ["TJ_VOICE_ID"],
    "Peter": os.environ["PETER_VOICE_ID"],
    "Indian": os.environ["INDIAN_VOICE_ID"]
}

MODEL = "qwen3.5-4b-32k-fast"  # any model on AssemblyAI's LLM Gateway

SYSTEM_PROMPT = """
You are the future version of the user, speaking to your younger self.
You share the same personality, memories, values, and speaking style
as the user, while reflecting greater wisdom, maturity, and life experience.

Your purpose is to help your younger self reflect on their life,
explore their potential, overcome challenges, and make better decisions.

Speak naturally, warmly, and honestly, as if you are having a
conversation with your past self, rather than acting as an AI assistant.

Do not present imagined future events as guaranteed facts.
Your replies are read out loud, so keep them to 1-3 short sentences
and never use markdown, lists, or emojis.
"""

messages = [{"role": "system", "content": SYSTEM_PROMPT}]
aai.settings.api_key = API_KEY
aai.settings.polling_interval = 0.5  # check transcription status every 0.5s instead of 3s

# One shared client keeps the connection open between turns (no new TLS handshake each time),
# and retries the connection up to 3 times if the network drops for a moment.
llm_client = httpx.Client(
    base_url="https://llm-gateway.assemblyai.com",
    headers={"Authorization": API_KEY},
    timeout=httpx.Timeout(30, connect=10),
    transport=httpx.HTTPTransport(retries=3),
)

# Allow the user to select a cloned voice
def select_voice():
    names = list(VOICES.keys())

    print("\nSelect your voice:")

    for i, name in enumerate(names, start=1):
        print(f"{i}. {name}")

    while True:
        choice = input("Select a number: ")

        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return VOICES[names[int(choice) - 1]]

        print("Invalid choice. Please try again.")

def listen():
    """Record from the mic until Enter is pressed, then transcribe it with AssemblyAI."""
    frames = []
    input("\nPress Enter and start talking...")

    with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16",
                           callback=lambda data, *_: frames.append(bytes(data))):
        input("Listening... press Enter when you're done.")

    # Save as wav file
    with wave.open("you.wav", "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"".join(frames))

    return aai.Transcriber().transcribe("you.wav").text or ""


# Send the user's input and conversation history to the LLM and return the generated response.
def think(user_text):
    """Send the conversation to the LLM and return its reply."""
    messages.append({"role": "user", "content": user_text})

    try:
        response = llm_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": messages, "max_tokens": 200},
        )
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        messages.pop()  # drop the unanswered question so the history stays clean
        raise

    messages.append({"role": "assistant", "content": reply})

    return reply


# Generate speech using the selected cloned voice
def speak(text, voice_id):
    config = aai.TTSConfig(voice_id=voice_id)

    with aai.TTSSession(config, api_key=API_KEY) as session:
        with sd.RawOutputStream(
            samplerate=24000,
            channels=1,
            dtype="int16"
        ) as speaker:
            for chunk in session.speak(text):
                speaker.write(chunk)


def main():
    # Select a cloned voice before starting the conversation.
    voice_id = select_voice()

    print("Dear Tomorrow is ready. Say 'goodbye' to exit.")

    while True:
        # A network hiccup in any step shouldn't end the conversation.
        try:
            user_text = listen().strip()

            if not user_text:
                print("(Didn't catch that, try again.)")
                continue

            print(f"You: {user_text}")

            if "goodbye" in user_text.lower():
                speak("Take care of yourself. See you in the future!", voice_id)
                break

            reply = think(user_text)
            print(f"Dear Tomorrow: {reply}")
            speak(reply, voice_id)

        except Exception as e:
            print(f"(Connection problem: {type(e).__name__}: {e}. Please say that again.)")

if __name__ == "__main__":
    main()