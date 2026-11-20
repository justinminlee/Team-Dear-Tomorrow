# Dear Tomorrow (voice)

A voice chat with your future self, in your own cloned voice. Over time it also learns
**how you talk** (filler words, slang, favourite phrases, tone) and replies in that style.

## Run

```
uv run main.py                 # normal conversation
uv run main.py --no-learning   # talk without saving anything for style learning
uv run main.py --reset-style   # delete everything learned for one voice
uv run pytest                  # run the tests (no API calls, everything is mocked)
```

`.env` needs `ASSEMBLYAI_API_KEY`, `TJ_VOICE_ID`, `PETER_VOICE_ID`, `INDIAN_VOICE_ID`.

Optional settings in `.env`:

| Setting | Default | Meaning |
|---|---|---|
| `STYLE_LEARNING_ENABLED` | `true` | Master switch for style learning |
| `LLM_ANALYSIS_BATCH_SIZE` | `1` | Run the LLM analysis after this many new transcripts (1 = every turn) |
| `STYLE_MIN_SAMPLES` | `2` | A habit must appear in this many separate turns before it shapes replies |
| `STYLE_MIN_OCCURRENCES` | `2` | ...and at least this many times in total |
| `DEAR_TOMORROW_DB` | `dear_tomorrow.db` | SQLite database path |
| `DEAR_TOMORROW_TRANSCRIPTS` | `transcripts/` | Where transcript text files go |

## Files

| File | Job |
|---|---|
| `main.py` | Voice selection, mic recording + STT, LLM reply, TTS playback, conversation loop, consent prompt, command-line options |
| `config.py` | Environment variables and settings |
| `prompts.py` | `build_system_prompt(style_profile)` |
| `transcript.py` | Append each user turn to one text file per voice (`transcripts/<voice>.txt`) |
| `style_analyzer.py` | Rule-based counting + LLM contextual analysis |
| `style_learner.py` | Merge new findings into the long-term profile |
| `style_worker.py` | Background thread so learning never slows down replies |
| `database.py` | SQLite tables and queries |

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

Transcripts, the database, recordings and logs stay on this computer and are git-ignored.
The app asks once per voice before learning, `--no-learning` skips it for a session, and
`--reset-style` deletes a voice's transcripts and profile. Logs contain IDs and counts only.
