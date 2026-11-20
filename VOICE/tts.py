"""Text to speech: read text out loud in a cloned voice."""
import assemblyai as aai
import sounddevice as sd

from config import API_KEY


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
