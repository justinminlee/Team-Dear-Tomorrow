# Supabase PostgreSQL 연결 및 DB 세션 관리
import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

# .env 파일 로드
load_dotenv()

# Fetch variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

# 필수 접속 정보가 .env에 있는지 확인
missing = [name for name, value in
           {"user": USER, "password": PASSWORD, "host": HOST, "port": PORT, "dbname": DBNAME}.items()
           if not value]
if missing:
    raise ValueError(f"Missing DB settings in .env file: {', '.join(missing)}")

# 환경변수에서 DB 연결 정보 가져오기
# requirements.txt에 있는 psycopg 3 드라이버를 사용 (postgresql+psycopg)
# URL.create는 비밀번호에 @, : 같은 특수문자가 있어도 안전하게 처리
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=USER,
    password=PASSWORD,
    host=HOST,
    port=int(PORT),
    database=DBNAME,
    query={"sslmode": "require"},
)

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
# Test the connection
try:
    with engine.connect() as connection:
        print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")


'''
# FastAPI 쪽 session.py
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
'''