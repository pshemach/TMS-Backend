"""SQLAlchemy engine and session factory."""

from sqlalchemy import create_engine, inspect, text
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


def _quote_table(name: str, dialect: str) -> str:
    return f"`{name}`" if dialect == "mysql" else f'"{name}"'


def _stale_model_tables(bind) -> list[tuple[str, str, set[str]]]:
    """Return (physical_name, model_name, missing_columns) for outdated tables.

    SQLite treats table names as case-insensitive, so a leftover ``orders``
    table prevents SQLAlchemy from creating the current ``Orders`` schema.
    """
    inspector = inspect(bind)
    existing = {name.lower(): name for name in inspector.get_table_names()}
    stale: list[tuple[str, str, set[str]]] = []
    for table in Base.metadata.sorted_tables:
        physical = existing.get(table.name.lower())
        if not physical:
            continue
        actual = {col["name"].lower() for col in inspector.get_columns(physical)}
        expected = {col.name.lower() for col in table.columns}
        missing = expected - actual
        if missing:
            stale.append((physical, table.name, missing))
    return stale


def _tables_to_drop(stale_physical_names: set[str]) -> set[str]:
    """Include model tables that foreign-key to a stale table."""
    drop = {name.lower() for name in stale_physical_names}
    changed = True
    while changed:
        changed = False
        for table in Base.metadata.tables.values():
            if table.name.lower() in drop:
                continue
            for fk in table.foreign_keys:
                if fk.column.table.name.lower() in drop:
                    drop.add(table.name.lower())
                    changed = True
                    break
    return drop


def ensure_schema(bind=None) -> None:
    """Create missing tables and rebuild leftover tables from older schemas."""
    # Import models here so table metadata is registered without a circular import.
    from src.infrastructure.database.models import Location as _Location  # noqa: F401

    bind = bind or engine
    Base.metadata.create_all(bind=bind)

    stale = _stale_model_tables(bind)
    if not stale:
        return

    dialect = bind.dialect.name
    drop_names = _tables_to_drop({physical for physical, _, _ in stale})
    print("Rebuilding outdated tables:")
    for physical, model_name, missing in stale:
        print(f"  {physical} -> {model_name} (missing: {', '.join(sorted(missing))})")

    with bind.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=OFF"))
        elif dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

        existing = {name.lower(): name for name in inspect(conn).get_table_names()}
        for lower_name in drop_names:
            physical = existing.get(lower_name)
            if not physical:
                continue
            conn.execute(text(f"DROP TABLE IF EXISTS {_quote_table(physical, dialect)}"))

        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        elif dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=ON"))

    Base.metadata.create_all(bind=bind)


ensure_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
