"""Speech to text: record from the mic and transcribe it."""
import wave

import assemblyai as aai
import sounddevice as sd

import config  # noqa: F401  (sets the AssemblyAI API key and polling interval)


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
