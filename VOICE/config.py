"""Shared settings: API key, voices, model, and speaking style learning options."""
import os
from pathlib import Path

import assemblyai as aai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["ASSEMBLYAI_API_KEY"]

# Store available cloned voices
VOICES = {
    "TJ": os.environ["TJ_VOICE_ID"],
    "Peter": os.environ["PETER_VOICE_ID"],
    "Lucas": os.environ["LUCAS_VOICE_ID"]
}

MODEL = "qwen3.5-4b-32k-fast"  # any model on AssemblyAI's LLM Gateway

aai.settings.api_key = API_KEY
aai.settings.polling_interval = 0.5  # check transcription status every 0.5s instead of 3s


def _env_flag(name, default):
    """Read a true/false setting from the environment."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# --- Speaking style learning -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Where learned data lives. All of these are git-ignored because they hold personal data.
DB_PATH = Path(os.getenv("DEAR_TOMORROW_DB", BASE_DIR / "dear_tomorrow.db"))
TRANSCRIPTS_DIR = Path(os.getenv("DEAR_TOMORROW_TRANSCRIPTS", BASE_DIR / "transcripts"))
LOG_PATH = Path(os.getenv("DEAR_TOMORROW_LOG", BASE_DIR / "dear_tomorrow.log"))

# Where the style database lives: "sqlite" (local file above) or "supabase".
# Supabase reuses the connection settings in backend/.env (user, password, host, port, dbname),
# so the password is kept in one place. The 4 style tables sit in the public schema next to the
# app's tables, locked with Row Level Security so the browser API can't read them.
STYLE_DB = os.getenv("STYLE_DB", "sqlite").strip().lower()
SUPABASE_ENV_FILE = Path(os.getenv("SUPABASE_ENV_FILE", BASE_DIR.parent / "backend" / ".env"))
SUPABASE_SCHEMA = os.getenv("SUPABASE_SCHEMA", "public")

# The future self is the user this many years from now (the questions ask about "10 years").
FUTURE_YEARS_AHEAD = int(os.getenv("FUTURE_YEARS_AHEAD", "10"))

# Master switch. Set STYLE_LEARNING_ENABLED=false in .env to turn learning off completely.
STYLE_LEARNING_ENABLED = _env_flag("STYLE_LEARNING_ENABLED", True)

# Run the LLM-based contextual analysis once this many new transcripts have piled up.
# 1 = after every turn, so the profile in the DB is updated as soon as each turn ends.
LLM_ANALYSIS_BATCH_SIZE = int(os.getenv("LLM_ANALYSIS_BATCH_SIZE", "1"))

# A habit only shapes replies after it shows up in at least this many separate turns
# and at least this many times in total, so one odd sentence never becomes a "habit".
STYLE_MIN_SAMPLES = int(os.getenv("STYLE_MIN_SAMPLES", "2"))
STYLE_MIN_OCCURRENCES = int(os.getenv("STYLE_MIN_OCCURRENCES", "2"))

# Keep the prompt compact: at most this many habits per category.
STYLE_MAX_PER_CATEGORY = 5

# Background worker limits.
STYLE_QUEUE_SIZE = 100       # queued tasks beyond this stay "pending" in the DB and are picked up later
STYLE_MAX_ATTEMPTS = 3       # give up on a transcript after this many failed analysis attempts
STYLE_SHUTDOWN_TIMEOUT = 20  # seconds to let queued analysis finish when the app closes
# At startup, wait up to this long for answers spoken on the website to be analysed.
STYLE_WARMUP_TIMEOUT = int(os.getenv("STYLE_WARMUP_TIMEOUT", "45"))
