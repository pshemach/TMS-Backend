"""
fix_matrix_status.py

One-off fix: any location still marked 'to_create' or 'to_update' that
already has at least one row in MatrixMaster (e.g. loaded via
ingest_from_csv.py) gets flipped to 'updated'.

Usage:
    python scripts/fix_matrix_status.py --dry-run
    python scripts/fix_matrix_status.py
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.database.models import GPSMaster, MatrixMaster
from src.infrastructure.database.session import SessionLocal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()

    try:
        pending = db.query(GPSMaster).filter(
            (GPSMaster.matrix_status == "to_create")
            | (GPSMaster.matrix_status == "to_update")
        ).all()

        ids_as_1 = {r[0] for r in db.query(MatrixMaster.shop_id_1).distinct()}
        ids_as_2 = {r[0] for r in db.query(MatrixMaster.shop_id_2).distinct()}
        with_matrix = ids_as_1 | ids_as_2

        to_fix = [s for s in pending if s.id in with_matrix]
        still_pending = [s for s in pending if s.id not in with_matrix]

        print(f"Locations currently to_create/to_update: {len(pending)}")
        print(f"  -> have matrix rows already, will mark 'updated': {len(to_fix)}")
        print(f"  -> no matrix rows found, left as-is: {len(still_pending)}")

        if still_pending:
            print("\nLocations left pending (no matrix data found for them):")
            for s in still_pending[:20]:
                print(f"  {s.shop_code} (id={s.id}, status={s.matrix_status})")
            if len(still_pending) > 20:
                print(f"  ... and {len(still_pending) - 20} more")

        if args.dry_run:
            print("\nDry run - no changes written.")
            return

        for s in to_fix:
            s.matrix_status = "updated"
        db.commit()
        print(f"\nDone. Updated {len(to_fix)} locations to matrix_status='updated'.")

    except Exception as e:
        db.rollback()
        print(f"ERROR - rolled back: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
