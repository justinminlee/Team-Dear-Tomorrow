"""Shared settings: API key, voices, model, and the system prompt."""
import os

import assemblyai as aai
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

aai.settings.api_key = API_KEY
aai.settings.polling_interval = 0.5  # check transcription status every 0.5s instead of 3s
