# Dear Tomorrow (voice)

A voice chat with your future self, in your own cloned voice. Before the chat it asks
**who you are** (the Future Self questionnaire), and over time it learns **how you talk**
(filler words, slang, favourite phrases, tone). Replies use both.

## Run

```
uv run main.py                 # log in, answer the questions, then talk
uv run main.py --skip-questions  # talk without logging in or answering the questions
uv run main.py --no-learning   # talk without saving anything for style learning
uv run main.py --learn         # ask the learning question again (turn learning back on)
uv run main.py --reset-style   # delete everything learned for one voice
uv run pytest                  # run the tests (no API calls, everything is mocked)
```

`.env` needs `ASSEMBLYAI_API_KEY`, `TJ_VOICE_ID`, `PETER_VOICE_ID`, `INDIAN_VOICE_ID`.

Login and the questionnaire need `STYLE_DB=supabase`, plus `SUPABASE_URL` and `SUPABASE_ANON_KEY`
in `backend/.env` (Supabase dashboard -> Project Settings -> API; the anon key, never the service key).

Optional settings in `.env`:

| Setting | Default | Meaning |
|---|---|---|
| `FUTURE_YEARS_AHEAD` | `10` | The future self is the user this many years from now |
| `STYLE_WARMUP_TIMEOUT` | `45` | At startup, wait this long for spoken website answers to be analysed |
| `STYLE_LEARNING_ENABLED` | `true` | Master switch for style learning |
| `LLM_ANALYSIS_BATCH_SIZE` | `1` | Run the LLM analysis after this many new transcripts (1 = every turn) |
| `STYLE_MIN_SAMPLES` | `2` | A habit must appear in this many separate turns before it shapes replies |
| `STYLE_MIN_OCCURRENCES` | `2` | ...and at least this many times in total |
| `STYLE_DB` | `sqlite` | `sqlite` = local file, `supabase` = Supabase PostgreSQL (connection settings are read from `backend/.env`) |
| `SUPABASE_SCHEMA` | `public` | Supabase schema for the 4 style tables (`dim_voice_style`, `fact_speaking_pattern`, `fact_transcript`, `fact_transcript_pattern`); RLS is turned on so the browser API can't read them |
| `DEAR_TOMORROW_DB` | `dear_tomorrow.db` | SQLite database path (when `STYLE_DB=sqlite`) |
| `DEAR_TOMORROW_TRANSCRIPTS` | `transcripts/` | Where the local copy of each turn's text goes |

## Files

| File | Job |
|---|---|
| `main.py` | Voice selection, mic recording + STT, LLM reply, TTS playback, conversation loop, consent prompt, command-line options |
| `config.py` | Environment variables and settings |
| `user_profile.py` | Supabase login, the questionnaire in the terminal, saving answers |
| `prompts.py` | `build_system_prompt(style_profile, user_profile)`: base persona + answers + speaking style |
| `transcript.py` | Keep a local copy of each user turn, one text file per voice (`transcripts/<voice>.txt`) |
| `style_analyzer.py` | Rule-based counting + LLM contextual analysis |
| `style_learner.py` | Merge new findings into the long-term profile |
| `style_worker.py` | Background thread so learning never slows down replies |
| `database.py` | Tables and queries; SQLite and Supabase (PostgreSQL) share the same SQL |

## Start: login and questionnaire

1. Log in with the same email and password as the website (Supabase Auth).
2. The questions of the active `future-self` questionnaire (`dim_question`) are shown one by one.
   Choices are picked by number; for "topics to avoid" type numbers separated by commas, or 0 for none.
3. Answers are saved to `fact_profile_answer` the same way the backend API does: a new row only for
   answers that changed, so the table keeps the history and the newest row is the current answer.
4. Next time, press Enter to reuse the saved answers, or type `edit` to review them (Enter keeps each one).
5. Every reply's system prompt includes the answers: your age + 10 years, your goals and values,
   the tone you asked for, topics to avoid, and the question you want to ask your future self.

## Spoken answers from the website

On the website's questionnaire, the free-text questions in "Your Future Self" are answered
out loud. The backend (`backend/app/api/voice_answers.py`) turns each recording into text with
AssemblyAI (same settings as this app, so "um" and slang are kept; the audio isn't stored) and,
once the answers are saved, queues them in `fact_transcript` for this user.

Speaking style belongs to the logged-in user, not to the cloned voice, so it follows them to any
voice. When this app starts, it analyses those waiting answers first (up to `STYLE_WARMUP_TIMEOUT`
seconds, default 45), so the first reply already uses the user's habits. Without logging in
(`--skip-questions`), style is stored per cloned voice as before.

## How learning works

```
listen() ─► user text ─┬─► think(text, voice_id) ─► speak()          (conversation, never waits)
                       │      └ loads the latest saved style profile
                       └─► save transcript file ─► queue ─► background worker
                                                            ├ rule counts (every turn)
                                                            ├ LLM analysis (every turn)
                                                            └ add to SQLite profile
```

* Only the user's own words are saved and analysed, never the AI's replies.
* Counts are always added to the totals, never replaced. Each (transcript, expression)
  pair is stored once, so retries and overlap between the rules and the LLM can't double count.
* A habit only reaches the prompt after it shows up in at least 2 separate turns, and the
  prompt gives its rate per 100 words so the reply uses it about as often as you do.
* Unfinished analysis is stored as `pending` in the database and resumes on the next start.

To teach the rules extra words, create `style_vocabulary.json` here:

```json
{"slang": ["innit", "cheers"], "common_expressions": ["fair enough"]}
```

## Privacy

Each turn's text is stored in the database (`fact_transcript.text`), which is what the analysis reads.
With `STYLE_DB=supabase` that text and the learned habits are in Supabase; the local transcript
copies, recordings and logs stay on this computer and are git-ignored.
The app asks once per voice before learning, `--no-learning` skips it for a session, and
`--reset-style` deletes a voice's transcripts and profile. Logs contain IDs and counts only.

## Tests

`uv run pytest` always uses a temporary SQLite file and never touches Supabase.
To run the same tests on the PostgreSQL code, set `VOICE_TEST_PG_URL` to a throwaway local database (each test creates and drops its own schema).
