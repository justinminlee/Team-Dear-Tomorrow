# Supabase PostgreSQL 연결 및 DB 세션 관리
import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

# backend/.env 파일 로드
BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

REQUIRED = ("user", "password", "host", "port", "dbname")
missing = [name for name in REQUIRED if not os.getenv(name)]
if missing:
    raise ValueError(f"Database settings missing in backend/.env: {', '.join(missing)}")

# URL.create escapes special characters in the password (e.g. @ / : #),
# which a plain f-string would break on.
# Supabase pooler hosts (*.pooler.supabase.com) need user = "postgres.<project-ref>".
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",  # psycopg v3, as listed in requirements.txt
    username=os.getenv("user"),
    password=os.getenv("password"),
    host=os.getenv("host"),
    port=int(os.getenv("port", "5432")),
    database=os.getenv("dbname"),
    query={"sslmode": "require"},
)

# PostgreSQL 연결 엔진 생성 (connects lazily, on first query)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# DB Session 생성 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
