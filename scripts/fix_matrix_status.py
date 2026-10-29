"""
fix_matrix_status.py

One-off fix: any shop still marked 'to_create' or 'to_update' but that
already has at least one row in MatrixMaster (i.e. its distances were
already loaded, e.g. via bulk_load_from_csv.py) gets flipped to 'updated'.

Usage:
    python fix_matrix_status.py --dry-run   # preview only
    python fix_matrix_status.py             # actually apply
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from src.database.database import get_db
from src.database.models import GPSMaster, MatrixMaster


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_gen = get_db()
    db = next(db_gen)

    try:
        pending_shops = db.query(GPSMaster).filter(
            (GPSMaster.matrix_status == "to_create") |
            (GPSMaster.matrix_status == "to_update")
        ).all()

        # All shop_ids that appear anywhere in MatrixMaster
        ids_as_1 = {r[0] for r in db.query(MatrixMaster.shop_id_1).distinct()}
        ids_as_2 = {r[0] for r in db.query(MatrixMaster.shop_id_2).distinct()}
        shops_with_matrix_rows = ids_as_1 | ids_as_2

        to_fix = [s for s in pending_shops if s.id in shops_with_matrix_rows]
        still_pending = [s for s in pending_shops if s.id not in shops_with_matrix_rows]

        print(f"Shops currently to_create/to_update: {len(pending_shops)}")
        print(f"  -> have matrix rows already, will mark 'updated': {len(to_fix)}")
        print(f"  -> no matrix rows found, left as-is: {len(still_pending)}")

        if still_pending:
            print("\nShops left pending (no matrix data found for them):")
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
        print(f"\nDone. Updated {len(to_fix)} shops to matrix_status='updated'.")

    except Exception as e:
        db.rollback()
        print(f"ERROR - rolled back: {e}")
        raise
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()