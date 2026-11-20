from pathlib import Path

import pytest

from transcript import (
    delete_voice_transcripts,
    read_transcript,
    save_transcript,
    voice_dir_name,
    voice_transcript_file,
)


def test_all_turns_for_a_voice_go_into_one_file(tdir):
    saved = [save_transcript(f"turn {i}", "voice_a", tdir) for i in range(20)]
    paths = {path for _, path in saved}
    assert paths == {Path(tdir).resolve() / "voice_a.txt"}
    assert len({tid for tid, _ in saved}) == 20  # every turn still gets its own id
    assert len(paths.pop().read_text(encoding="utf-8").splitlines()) == 20


def test_earlier_turns_are_never_overwritten(tdir):
    first, path = save_transcript("first", "voice_a", tdir)
    save_transcript("second", "voice_a", tdir)
    assert read_transcript(path, tdir, first) == "first"


def test_each_turn_can_be_read_back_by_id(tdir):
    a, path = save_transcript("um bro", "voice_a", tdir)
    b, _ = save_transcript("yeah nah", "voice_a", tdir)
    assert read_transcript(path, tdir, a) == "um bro"
    assert read_transcript(path, tdir, b) == "yeah nah"
    with pytest.raises(LookupError):
        read_transcript(path, tdir, "missing")


def test_line_format_and_utf8(tdir):
    tid, path = save_transcript("  café, naïve — 안녕  ", "voice_a", tdir)
    stamp, line_id, text = path.read_text(encoding="utf-8").rstrip("\n").split("\t")
    assert (line_id, text) == (tid, "café, naïve — 안녕")
    assert len(stamp) == len("2026-11-21 02:13:12")


def test_tabs_and_newlines_cannot_break_the_format(tdir):
    tid, path = save_transcript("one\ttwo\nthree", "voice_a", tdir)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert read_transcript(path, tdir, tid) == "one two three"


def test_known_voices_use_their_name_as_file_name(tdir):
    # conftest sets INDIAN_VOICE_ID=voice_indian and TJ_VOICE_ID=voice_tj
    assert save_transcript("hi", "voice_indian", tdir)[1].name == "indian.txt"
    assert save_transcript("hi", "voice_tj", tdir)[1].name == "tj.txt"


def test_voices_get_separate_files(tdir):
    _, a = save_transcript("one", "voice_a", tdir)
    _, b = save_transcript("two", "voice_b", tdir)
    assert a != b


def test_empty_transcript_is_rejected(tdir):
    with pytest.raises(ValueError):
        save_transcript("   ", "voice_a", tdir)


@pytest.mark.parametrize("voice_id", ["../../etc", "..\\..\\windows", "a/b", "/abs"])
def test_unsafe_voice_ids_stay_inside_folder(tdir, voice_id):
    _, path = save_transcript("hi", voice_id, tdir)
    assert path.parent == Path(tdir).resolve()
    assert "/" not in voice_dir_name(voice_id) and "\\" not in voice_dir_name(voice_id)


def test_voice_id_with_no_safe_characters_is_rejected(tdir):
    with pytest.raises(ValueError):
        save_transcript("hi", "../..", tdir)


def test_read_refuses_paths_outside_transcripts(tmp_path, tdir):
    outside = tmp_path / "secret.txt"
    outside.write_text("2026-01-01 00:00:00\tx\tnope\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_transcript(outside, tdir, "x")


def test_delete_voice_transcripts(tdir):
    save_transcript("hi", "voice_a", tdir)
    save_transcript("hi", "voice_b", tdir)
    delete_voice_transcripts("voice_a", tdir)
    assert not voice_transcript_file("voice_a", tdir).exists()
    assert voice_transcript_file("voice_b", tdir).exists()
