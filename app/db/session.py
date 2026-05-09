from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict[str, object]:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


_url = get_settings().database_url
_engine_kwargs = {
    "connect_args": _connect_args(_url),
    "pool_pre_ping": True,
}
if _url == "sqlite:///:memory:":
    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
