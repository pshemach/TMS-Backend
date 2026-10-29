"""Drop and recreate all tables (schema redesign / local reset).

WARNING: destroys all data in the configured database.

Usage:
    python scripts/reset_db.py
    python scripts/reset_db.py --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect, text

from src.infrastructure.database import models  # noqa: F401 — register metadata
from src.infrastructure.database.base import Base
from src.infrastructure.database.session import engine


def reset_schema() -> None:
    print(f"Dropping all tables on {engine.url} ...")
    dialect = engine.dialect.name

    with engine.begin() as conn:
        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        elif dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=OFF"))

        # Drop every physical table (old + new names), FK checks off.
        table_names = inspect(conn).get_table_names()
        for table_name in table_names:
            quoted = f"`{table_name}`" if dialect == "mysql" else f'"{table_name}"'
            conn.execute(text(f"DROP TABLE IF EXISTS {quoted}"))
            print(f"  dropped: {table_name}")

        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        elif dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=ON"))

    print("Creating tables ...")
    Base.metadata.create_all(bind=engine)
    print("Done. Schema recreated.")
    print("Tables:", ", ".join(sorted(Base.metadata.tables.keys())))


def main() -> None:
    parser = argparse.ArgumentParser(description="Drop and recreate TMS database schema")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if not args.yes:
        reply = input(
            "This will DELETE ALL DATA and recreate tables. Type 'yes' to continue: "
        ).strip()
        if reply.lower() != "yes":
            print("Aborted.")
            sys.exit(1)

    reset_schema()


if __name__ == "__main__":
    main()
