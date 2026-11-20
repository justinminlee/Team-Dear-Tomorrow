"""Save the user's transcripts: one UTF-8 text file per voice, one line per turn.

The file is named after the voice, e.g. transcripts/indian.txt for the "Indian" voice.

Each line looks like:
    2026-11-21 02:13:12<TAB>ee218ac009eb40ea87c4695a4cd1ad80<TAB>Hello. Um. Damn.

The middle column is the transcript id stored in the database, so the analyzer can find
a single turn again. New lines are only ever appended; earlier turns are never changed.
"""
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from config import VOICES

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]")
_append_lock = threading.Lock()


def voice_dir_name(voice_id):
    """Turn a Voice ID into a safe file name (no slashes, dots or other path tricks)."""
    name = _UNSAFE_CHARS.sub("_", str(voice_id)).strip("_")[:64]
    if not name:
        raise ValueError("Voice ID cannot be turned into a safe file name.")
    return name


def voice_file_label(voice_id):
    """File name for a voice: its display name in lowercase (e.g. "indian"), or the ID if unknown."""
    for name, vid in VOICES.items():
        if vid == voice_id:
            return name.lower()
    return voice_id


def voice_transcript_file(voice_id, base_dir):
    """Path of the voice's transcript file (e.g. transcripts/indian.txt), always directly inside base_dir."""
    base = Path(base_dir).resolve()
    path = (base / f"{voice_dir_name(voice_file_label(voice_id))}.txt").resolve()
    if path.parent != base:
        raise ValueError("Unsafe transcript path.")
    return path


def save_transcript(text, voice_id, base_dir):
    """Append the user's words to the voice's file and return (transcript_id, path).

    The whole line is written in one go and flushed to disk before this returns, so the
    analyzer never reads a half-written turn.
    """
    # Tabs and newlines would break the one-line-per-turn format.
    text = " ".join((text or "").split())
    if not text:
        raise ValueError("Refusing to save an empty transcript.")

    path = voice_transcript_file(voice_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    transcript_id = uuid.uuid4().hex
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{transcript_id}\t{text}\n"

    with _append_lock:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    return transcript_id, path


def read_transcript(path, base_dir, transcript_id):
    """Return the text of one turn from a voice's transcript file.

    Refuses any path outside the transcripts folder. Raises LookupError if the id isn't there.
    """
    base = Path(base_dir).resolve()
    resolved = Path(path).resolve()
    if resolved.parent != base:
        raise ValueError("Transcript path is outside the transcripts folder.")

    with open(resolved, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) == 3 and parts[1] == transcript_id:
                return parts[2].strip()
    raise LookupError(f"Transcript {transcript_id} not found in {resolved.name}")


def delete_voice_transcripts(voice_id, base_dir):
    """Delete the voice's transcript file."""
    path = voice_transcript_file(voice_id, base_dir)
    path.unlink(missing_ok=True)
