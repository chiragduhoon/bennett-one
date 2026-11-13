from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


def SessionLocal() -> Session:
    return sessionmaker(bind=engine(), expire_on_commit=False)()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
