"""Speech to text: record from the mic and transcribe it."""
import wave

import assemblyai as aai
import sounddevice as sd

import config  # noqa: F401


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
        disfluencies=True,
        filter_profanity=False,
        format_text=False,
        language_code="en"
    )

    # Transcribe the recorded audio.
    transcript = aai.Transcriber(
        config=transcription_config
    ).transcribe("you.wav")

    # Handle transcription errors.
    if transcript.error:
        raise RuntimeError(transcript.error)

    return transcript.text or ""