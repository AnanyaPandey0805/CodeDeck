from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

import logging
try:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
except Exception as exc:
    logger = logging.getLogger('deploymind')
    logger.warning('Postgres driver not available, falling back to SQLite in-memory: %s', exc)
    engine = create_engine('sqlite:///:memory:', pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
