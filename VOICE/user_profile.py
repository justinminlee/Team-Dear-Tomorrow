"""Who the user is: Supabase login and the Future Self questionnaire.

Before the voice chat starts, the user logs in with the same email and password as the
web app, then answers the questions in public.dim_question. Answers are saved to
public.fact_profile_answer exactly like the backend API does (backend/app/api/questionnaire.py):
an append-only history where a new row is added only when an answer changed, and the
latest row per question is the current answer.
"""
import hashlib
import logging
import math
import os
from getpass import getpass
from pathlib import Path

import httpx
from dotenv import dotenv_values

import config

log = logging.getLogger(__name__)

QUESTIONNAIRE_CODE = "future-self"
MAX_TEXT_LENGTH = 2000
DEFAULT_SCALE = (1, 10)

# Free-text questions in these sections are answered out loud (same rule as the website,
# frontend/src/api/questionnaire.ts). Spoken answers also teach the app how the user talks.
VOICE_SECTIONS = {"Your Future Self"}


def is_voice_question(question):
    return question["response_type"] == "text" and question["category"] in VOICE_SECTIONS


def sample_id(user_id, question_id, spoken):
    """Same id as the website uses (backend/app/api/voice_answers.py), so an answer spoken
    in either place is stored as a style sample only once."""
    return "q" + hashlib.sha256(f"{user_id}:{question_id}:{spoken}".encode()).hexdigest()[:31]


class LoginError(Exception):
    """Wrong email or password, or the email isn't confirmed yet. The user can try again."""


class LoginUnavailable(LoginError):
    """Login can't work right now (not configured, or Supabase unreachable). Retrying won't help."""


# --- Login ----------------------------------------------------------------------

def auth_settings(env_file=None):
    """SUPABASE_URL and SUPABASE_ANON_KEY, from the environment or backend/.env."""
    env_file = Path(env_file or config.SUPABASE_ENV_FILE)
    values = dotenv_values(env_file) if env_file.exists() else {}
    url = (os.getenv("SUPABASE_URL") or values.get("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY") or values.get("SUPABASE_ANON_KEY") or ""
    if not url or not key:
        raise LoginUnavailable(
            "Supabase login is not set up. Add SUPABASE_URL and SUPABASE_ANON_KEY to backend/.env "
            "(Supabase dashboard -> Project Settings -> API)."
        )
    return url, key


def sign_in(email, password, client=None, settings=None):
    """Log in with Supabase Auth. Returns {"id", "email", "display_name"}."""
    url, key = settings or auth_settings()
    own_client = client is None
    client = client or httpx.Client(timeout=15)
    try:
        response = client.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
    except httpx.RequestError as e:
        raise LoginUnavailable(f"Could not reach Supabase ({type(e).__name__}).") from None
    finally:
        if own_client:
            client.close()
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code != 200 or not (data.get("user") or {}).get("id"):
        reason = data.get("msg") or data.get("error_description") or data.get("message") or "login failed"
        raise LoginError(str(reason))
    user = data["user"]
    meta = user.get("user_metadata") or {}
    return {"id": user["id"], "email": user.get("email") or email,
            "display_name": meta.get("username") or meta.get("display_name") or None}


def login(input_fn=input, password_fn=getpass, sign_in_fn=sign_in, attempts=3):
    """Ask for email and password until login works (up to `attempts` tries)."""
    print("\nLog in with your Dear Tomorrow account (the same one you use on the website).")
    for attempt in range(1, attempts + 1):
        email = input_fn("Email: ").strip()
        password = password_fn("Password (hidden): ")
        if not email or not password:
            print("Please enter both your email and password.")
            continue
        try:
            user = sign_in_fn(email, password)
            print(f"Logged in as {user['display_name'] or user['email']}.")
            return user
        except LoginUnavailable:
            raise
        except LoginError as e:
            left = attempts - attempt
            print(f"Login failed: {e}." + (f" {left} tries left." if left else ""))
    raise LoginError("Too many failed login attempts.")


# --- Questions and answers (same rules as the backend API) ----------------------

def option_list(options):
    """dim_question.options may be ["A", "B"] or [{"value", "label"}]."""
    if not isinstance(options, list):
        return []
    result = []
    for item in options:
        if isinstance(item, str):
            result.append({"value": item, "label": item})
        elif isinstance(item, dict) and item.get("value") is not None:
            value = str(item["value"])
            result.append({"value": value, "label": str(item.get("label") or value)})
    return result


def number_range(question):
    """min/max from options like {"min": 1, "max": 10}; scales default to 1-10."""
    opts = question["options"] if isinstance(question.get("options"), dict) else {}
    lo, hi = opts.get("min"), opts.get("max")
    if question["response_type"] == "scale":
        lo = DEFAULT_SCALE[0] if lo is None else lo
        hi = DEFAULT_SCALE[1] if hi is None else hi
    return lo, hi


def validate_answer(question, value):
    """Return the cleaned value to store, or raise ValueError with a reason."""
    kind = question["response_type"]

    if kind == "text":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("please type an answer")
        if len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"please keep it under {MAX_TEXT_LENGTH} characters")
        return value.strip()

    if kind in ("number", "scale"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("please enter a number")
        if kind == "scale" and value != int(value):
            raise ValueError("please enter a whole number")
        lo, hi = number_range(question)
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            raise ValueError(f"please enter a number between {lo} and {hi}")
        return int(value) if value == int(value) else value

    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError("please answer y or n")
        return value

    allowed = {o["value"] for o in option_list(question.get("options"))}
    if kind == "single_choice":
        if not isinstance(value, str) or value not in allowed:
            raise ValueError("please pick one of the numbers")
        return value

    if kind == "multiple_choice":
        if not isinstance(value, list) or any(v not in allowed for v in value):
            raise ValueError("please pick from the numbers shown")
        return list(dict.fromkeys(value))  # drop duplicates, keep order

    raise ValueError(f"unsupported question type '{kind}'")


def parse_input(question, raw):
    """Turn what the user typed into an answer value (then checked by validate_answer)."""
    kind = question["response_type"]
    raw = raw.strip()
    if kind == "text":
        return raw
    if kind in ("number", "scale"):
        try:
            number = float(raw)
        except ValueError:
            raise ValueError("please enter a number") from None
        return int(number) if number.is_integer() else number
    if kind == "boolean":
        if raw.lower() in {"y", "yes"}:
            return True
        if raw.lower() in {"n", "no"}:
            return False
        raise ValueError("please answer y or n")
    options = option_list(question.get("options"))
    if kind == "single_choice":
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]["value"]
        raise ValueError(f"please enter a number from 1 to {len(options)}")
    if kind == "multiple_choice":
        if not raw or raw == "0":
            return []
        picks = [p.strip() for p in raw.replace(" ", ",").split(",") if p.strip()]
        if not all(p.isdigit() and 1 <= int(p) <= len(options) for p in picks):
            raise ValueError(f"please enter numbers from 1 to {len(options)}, separated by commas")
        return [options[int(p) - 1]["value"] for p in picks]
    raise ValueError(f"unsupported question type '{kind}'")


def format_answer(question, value):
    """Answer as plain text, for the screen and the system prompt."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else "none"
    return str(value)


def ask_question(question, number, total, current=None, input_fn=input):
    """Show one question and keep asking until the answer is valid. Enter keeps `current`."""
    kind = question["response_type"]
    print(f"\n[{number}/{total}] {question['category']}")
    print(question["question_text"])
    options = option_list(question.get("options"))
    if kind in ("single_choice", "multiple_choice"):
        for i, option in enumerate(options, start=1):
            print(f"  {i}. {option['label']}")

    hints = {
        "number": "a number",
        "scale": "a number from {} to {}".format(*number_range(question)),
        "single_choice": "the number of one option",
        "multiple_choice": "numbers separated by commas, or 0 for none",
        "boolean": "y or n",
        "text": "your answer",
    }
    hint = hints.get(kind, "your answer")
    if current is not None:
        hint += f"; Enter keeps: {format_answer(question, current)}"

    while True:
        raw = input_fn(f"({hint}) > ")
        if not raw.strip() and current is not None:
            return current
        try:
            return validate_answer(question, parse_input(question, raw))
        except ValueError as e:
            print(f"  {str(e).capitalize()}.")


def ask_spoken_question(question, number, total, current, listen_fn, input_fn=input):
    """Answer one question out loud. Returns (answer, spoken).

    Enter keeps a saved answer. If recording keeps failing, the user can type instead.
    """
    print(f"\n[{number}/{total}] {question['category']}")
    print(question["question_text"])
    print("(Answer out loud. Your words become the answer and help your future self talk like you.)")
    if current is not None:
        print(f'  Saved answer: "{format_answer(question, current)}"')
        if not input_fn("(Enter keeps it, or type r to record a new one) > ").strip():
            return current, False

    while True:
        try:
            spoken = " ".join((listen_fn() or "").split())
        except Exception as e:
            log.warning("Recording an answer failed: %s", type(e).__name__)
            spoken = ""
            print(f"  Couldn't record that ({type(e).__name__}).")
        if not spoken:
            choice = input_fn("  I didn't catch that. Press Enter to try again, or type t to type instead > ")
            if choice.strip().lower() == "t":
                return ask_question(question, number, total, current, input_fn), False
            continue
        try:
            spoken = validate_answer(question, spoken)
        except ValueError as e:
            print(f"  {str(e).capitalize()}. Let's try again.")
            continue
        print(f'  You said: "{spoken}"')
        if input_fn("(Enter keeps it, or type r to record again) > ").strip().lower() != "r":
            return spoken, True


def run_questionnaire(questions, latest, input_fn=input, listen_fn=None, spoken=None):
    """Ask every question. Returns {question_id: answer} for all of them.

    With listen_fn, voice questions are answered out loud; the ids of answers that were
    actually spoken this time are added to the `spoken` set.
    """
    if latest and all(q["question_id"] in latest for q in questions):
        print("\nYou've already answered all the questions.")
        while True:
            choice = input_fn("Press Enter to use your saved answers, or type 'edit' to review them: ")
            if not choice.strip():
                return {q["question_id"]: latest[q["question_id"]] for q in questions}
            if choice.strip().lower() == "edit":
                break
    else:
        print(f"\nBefore we talk, tell me about yourself ({len(questions)} questions).")
        print("Your future self will use these answers in every conversation.")

    answers = {}
    for i, q in enumerate(questions, start=1):
        current = latest.get(q["question_id"])
        if listen_fn and is_voice_question(q):
            answers[q["question_id"]], was_spoken = ask_spoken_question(
                q, i, len(questions), current, listen_fn, input_fn)
            if was_spoken and spoken is not None:
                spoken.add(q["question_id"])
        else:
            answers[q["question_id"]] = ask_question(q, i, len(questions), current, input_fn)
    return answers


# --- Database ---------------------------------------------------------------------

class ProfileStore:
    """Reads questions and saves answers in the app's own tables (Supabase public schema)."""

    def __init__(self, db):
        if getattr(db, "pool", None) is None:
            raise RuntimeError("The questionnaire needs the Supabase database (STYLE_DB=supabase).")
        self.db = db
        self.pool = db.pool

    def load_questions(self):
        """Active questions of the newest active 'future-self' questionnaire, in display order."""
        with self.pool.connection() as conn:
            questionnaire = conn.execute(
                "SELECT questionnaire_id FROM dim_questionnaire "
                "WHERE questionnaire_code = %s AND is_active ORDER BY version DESC LIMIT 1",
                (QUESTIONNAIRE_CODE,),
            ).fetchone()
            if questionnaire is None:
                return []
            return conn.execute(
                "SELECT question_id, question_code, category, question_text, response_type, options, display_order "
                "FROM dim_question WHERE questionnaire_id = %s AND is_active "
                "ORDER BY display_order, question_code",
                (questionnaire["questionnaire_id"],),
            ).fetchall()

    def load_latest_answers(self, user_id):
        """{question_id: answer_value}: the newest answer per question."""
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ON (question_id) question_id, answer_value FROM fact_profile_answer "
                "WHERE user_id = %s ORDER BY question_id, answered_at DESC",
                (user_id,),
            ).fetchall()
        return {r["question_id"]: r["answer_value"] for r in rows}

    def save_answers(self, user, answers):
        """Insert a row only for answers that changed. Returns how many were saved."""
        from psycopg.types.json import Jsonb

        latest = self.load_latest_answers(user["id"])
        missing = object()
        changed = {qid: v for qid, v in answers.items() if latest.get(qid, missing) != v}
        if not changed:
            return 0
        with self.pool.connection() as conn:  # one transaction: all answers are saved, or none
            # fact_profile_answer.user_id references dim_user_profile, so make sure the row exists.
            conn.execute(
                "INSERT INTO dim_user_profile (user_id, display_name) VALUES (%s, %s) "
                "ON CONFLICT (user_id) DO NOTHING",
                (user["id"], user.get("display_name")),
            )
            conn.cursor().executemany(
                "INSERT INTO fact_profile_answer (user_id, question_id, answer_value) VALUES (%s, %s, %s)",
                [(user["id"], qid, Jsonb(value)) for qid, value in changed.items()],
            )
        return len(changed)


    def save_voice_samples(self, user, samples):
        """Queue spoken answers as speaking-style samples for this user. Returns how many were new.

        Answering out loud counts as agreeing to style learning (the question says so).
        They are analysed when the chat starts, like samples spoken on the website.
        """
        from style_analyzer import word_count

        key = str(user["id"])
        self.db.ensure_profile(key, user.get("display_name"))
        self.db.set_learning_consent(key, True)
        return sum(
            self.db.register_transcript(sample_id(key, qid, text), key, text, word_count(text))
            for qid, text in samples
        )


def user_profile_for_prompt(questions, answers):
    """Pair each question with its answer, ready for prompts.build_profile_section()."""
    return [
        {"code": q["question_code"], "category": q["category"], "question": q["question_text"],
         "answer": format_answer(q, answers[q["question_id"]]), "value": answers[q["question_id"]]}
        for q in questions if q["question_id"] in answers
    ]


def setup_profile(db, input_fn=input, login_fn=login, listen_fn=None):
    """Log in, run the questionnaire and save it. Returns (user, prompt-ready profile list).

    listen_fn records and transcribes one answer; without it every question is typed.
    """
    user = login_fn()
    store = ProfileStore(db)
    questions = store.load_questions()
    if not questions:
        print("(No questionnaire found in the database, so I'll skip the questions.)")
        return user, []
    spoken = set()
    answers = run_questionnaire(questions, store.load_latest_answers(user["id"]), input_fn, listen_fn, spoken)
    saved = store.save_answers(user, answers)
    print(f"\nSaved {saved} new answer{'s' if saved != 1 else ''}." if saved else "\nUsing your saved answers.")
    if spoken:
        try:
            store.save_voice_samples(user, [(qid, answers[qid]) for qid in spoken])
        except Exception:
            log.exception("Could not queue spoken answers for style learning")
            print("(Couldn't save your spoken answers for style learning this time.)")
    return user, user_profile_for_prompt(questions, answers)
