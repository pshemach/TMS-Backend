"""One-shot: rewrite uppercase enum *names* to lowercase *values* in existing rows."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from src.infrastructure.database.session import SessionLocal

# (table, column, name -> value)
MAPPINGS = [
    (
        "Location",
        "LocationType",
        {"CUSTOMER": "customer", "DEPOT": "depot", "customer": "customer", "depot": "depot"},
    ),
    (
        "Location",
        "MatrixStatus",
        {
            "TO_CREATE": "to_create",
            "TO_UPDATE": "to_update",
            "UPDATED": "updated",
            "to_create": "to_create",
            "to_update": "to_update",
            "updated": "updated",
        },
    ),
    (
        "Orders",
        "Status",
        {
            "PENDING": "pending",
            "PLANED": "planed",
            "ACTIVE": "active",
            "COMPLETED": "completed",
            "pending": "pending",
            "planed": "planed",
            "active": "active",
            "completed": "completed",
        },
    ),
    (
        "Orders",
        "Priority",
        {
            "LOW": "low",
            "MEDIUM": "medium",
            "HIGH": "high",
            "low": "low",
            "medium": "medium",
            "high": "high",
        },
    ),
    (
        "Job",
        "Status",
        {
            "RUNNING": "running",
            "PLANNED": "planned",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "running": "running",
            "planned": "planned",
            "completed": "completed",
            "failed": "failed",
        },
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        # Show column types (MySQL); ignore on SQLite
        try:
            rows = db.execute(
                text(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND COLUMN_NAME IN ('LocationType','MatrixStatus','Status','Priority')
                    ORDER BY TABLE_NAME, COLUMN_NAME
                    """
                )
            ).fetchall()
            print("Column types:")
            for r in rows:
                print(f"  {r.TABLE_NAME}.{r.COLUMN_NAME}: {r.COLUMN_TYPE}")
        except Exception as exc:
            print(f"(skip column-type probe: {exc})")

        # Widen to VARCHAR so lowercase values are allowed even if column was native ENUM
        alters = [
            "ALTER TABLE Location MODIFY COLUMN LocationType VARCHAR(20) NOT NULL",
            "ALTER TABLE Location MODIFY COLUMN MatrixStatus VARCHAR(20) NOT NULL",
            "ALTER TABLE Orders MODIFY COLUMN Status VARCHAR(20) NOT NULL",
            "ALTER TABLE Orders MODIFY COLUMN Priority VARCHAR(20) NULL",
            "ALTER TABLE Job MODIFY COLUMN Status VARCHAR(20) NOT NULL",
        ]
        for sql in alters:
            try:
                db.execute(text(sql))
                print(f"OK: {sql}")
            except Exception as exc:
                print(f"skip alter ({exc}): {sql}")

        for table, column, mapping in MAPPINGS:
            for old, new in mapping.items():
                if old == new:
                    continue
                result = db.execute(
                    text(f"UPDATE `{table}` SET `{column}` = :new WHERE `{column}` = :old"),
                    {"old": old, "new": new},
                )
                if result.rowcount:
                    print(f"{table}.{column}: {old!r} -> {new!r} ({result.rowcount} rows)")

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
