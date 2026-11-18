# SQLAlchemy 모델의 공통 부모 클래스 정의
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass