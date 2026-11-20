"""Standalone speaker analysis and explicit DB saving."""

import argparse
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from speaker_feature_analysis import (
    SpeakerProfile,
    analyze_files,
)


BASE_DIR = Path(__file__).resolve().parent


def local_path(value: str) -> Path:
    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    return BASE_DIR / path


def main():
    load_dotenv(BASE_DIR / ".env")

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    analyze = commands.add_parser(
        "analyze",
        help="Analyze WAV recordings and save local JSON",
    )

    analyze.add_argument(
        "--speaker",
        required=True,
    )

    analyze.add_argument(
        "--voice-env",
        required=True,
    )

    analyze.add_argument(
        "--audio",
        action="append",
        required=True,
        help="Repeat this option for multiple recordings",
    )

    save = commands.add_parser(
        "save",
        help="Save a reviewed JSON result without reanalysis",
    )

    save.add_argument(
        "--file",
        required=True,
    )

    save.add_argument(
        "--init-db",
        action="store_true",
    )

    save.add_argument(
        "--replace",
        action="store_true",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        api_key = os.getenv(
            "ASSEMBLYAI_API_KEY", ""
        ).strip()

        voice_id = os.getenv(
            args.voice_env, ""
        ).strip()

        if not api_key or not voice_id:
            raise RuntimeError(
                "Configure ASSEMBLYAI_API_KEY and the "
                "selected voice ID in VOICE/.env."
            )

        profile = analyze_files(
            paths=[
                local_path(path)
                for path in args.audio
            ],
            speaker=args.speaker,
            voice_id=voice_id,
            api_key=api_key,
            model=os.getenv(
                "ASSEMBLYAI_LLM_MODEL",
                "qwen3.5-4b-32k-fast",
            ),
        )

        directory = BASE_DIR / "speaker_feature_output"
        directory.mkdir(exist_ok=True)

        # Ignore generated results without changing root .gitignore.
        ignore_file = directory / ".gitignore"

        if not ignore_file.exists():
            ignore_file.write_text(
                "*\n!.gitignore\n",
                encoding="utf-8",
            )

        output = directory / (
            f"profile-{uuid4().hex}.json"
        )

        with output.open(
            "x",
            encoding="utf-8",
        ) as stream:
            stream.write(
                profile.model_dump_json(indent=2)
            )

        print(
            f"Local result: {output.relative_to(BASE_DIR)}"
        )

        print(
            "No DB writes. Accent is not assessed. "
            "Review the JSON before saving."
        )

    else:
        # DB dependencies are loaded only when saving.
        from speaker_feature_store import save_profile

        profile = SpeakerProfile.model_validate_json(
            local_path(args.file).read_text(
                encoding="utf-8"
            )
        )

        if not profile.speaking_style.traits:
            raise ValueError(
                "No verified style traits. Record more "
                "speech before DB enrollment."
            )

        save_profile(
            profile,
            initialize=args.init_db,
            replace=args.replace,
        )

        print(
            f"Saved profile for {profile.speaker_key}. "
            "No audio bytes were stored."
        )


if __name__ == "__main__":
    main()
    