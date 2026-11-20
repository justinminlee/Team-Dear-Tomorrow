"""Optional PostgreSQL storage for speaker analysis."""

import os
from pathlib import Path

from dotenv import dotenv_values

from speaker_feature_analysis import SpeakerProfile


BASE_DIR = Path(__file__).resolve().parent


def connect_db():
    # Required only for DB commands.
    import psycopg

    config = {
        **dotenv_values(
            BASE_DIR.parent / "backend" / ".env"
        ),
        **dotenv_values(BASE_DIR / ".env"),
        **os.environ,
    }

    database_url = config.get("DATABASE_URL")

    if database_url:
        database_url = database_url.replace(
            "postgresql+psycopg2://",
            "postgresql://",
            1,
        )

        database_url = database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )

        return psycopg.connect(
            database_url,
            connect_timeout=10,
        )

    required = [
        "user",
        "password",
        "host",
        "port",
        "dbname",
    ]

    if any(not config.get(key) for key in required):
        raise RuntimeError(
            "Configure DATABASE_URL or "
            "user/password/host/port/dbname in .env."
        )

    return psycopg.connect(
        **{
            key: config[key]
            for key in required
        },
        sslmode="require",
        connect_timeout=10,
    )


def save_profile(
    profile: SpeakerProfile,
    initialize: bool = False,
    replace: bool = False,
):
    from psycopg.types.json import Jsonb

    with connect_db() as connection:
        if initialize:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS
                public.speaker_feature_profiles (
                    speaker_key TEXT PRIMARY KEY,
                    provider_voice_id TEXT NOT NULL,
                    features JSONB NOT NULL
                )
            """)

        statement = """
            INSERT INTO public.speaker_feature_profiles
                (speaker_key, provider_voice_id, features)
            VALUES (%s, %s, %s)
        """

        if replace:
            statement += """
                ON CONFLICT (speaker_key)
                DO UPDATE SET
                    provider_voice_id =
                        EXCLUDED.provider_voice_id,
                    features = EXCLUDED.features
            """

        connection.execute(
            statement,
            (
                profile.speaker_key,
                profile.provider_voice_id,
                Jsonb(profile.model_dump()),
            ),
        )


def load_profile(
    speaker_key: str,
) -> SpeakerProfile | None:
    with connect_db() as connection:
        row = connection.execute(
            """
            SELECT features
            FROM public.speaker_feature_profiles
            WHERE speaker_key = %s
            """,
            (speaker_key,),
        ).fetchone()

    if row is None:
        return None

    return SpeakerProfile.model_validate(row[0])