"""SQLAlchemy engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure import config
from src.infrastructure.config import ensure_directories
from src.infrastructure.database.base import Base

ensure_directories()

connect_args = {}
if "sqlite" in config.DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    config.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def ensure_schema() -> None:
    """Create any missing tables. Safe to call more than once."""
    # Import models here so table metadata is registered without a circular import.
    from src.infrastructure.database.models import Location as _Location  # noqa: F401

    Base.metadata.create_all(bind=engine)


ensure_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
