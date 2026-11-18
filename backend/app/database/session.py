# Supabase PostgreSQL 연결 및 DB 세션 관리
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# .env 파일 로드
load_dotenv()

# 환경변수에서 DB 연결 정보 가져오기
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env file")

# PostgreSQL 연결 엔진 생성
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# DB Session 생성 설정
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)



'''
# FastAPI 쪽 session.py
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
'''