"""Create random dummy orders from existing customers.

Requires at least one active customer (`Location` with location_type=customer).

Usage:
    python scripts/seed_dummy_orders.py
    python scripts/seed_dummy_orders.py --count 200
    python scripts/seed_dummy_orders.py --count 50 --dry-run
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.database.models import (
    Location,
    LocationType,
    Order,
    OrderStatus,
    Priority,
)
from src.infrastructure.database.session import SessionLocal, engine

PRIORITIES = [ Priority.MEDIUM]
TIME_WINDOWS = [
    (None, None),  # no window
]


def _unique_order_id(db, used: set[str]) -> str:
    for _ in range(50):
        oid = f"PO-DUMMY-{datetime.utcnow().strftime('%y%m%d')}-{random.randint(10000, 99999)}"
        if oid in used:
            continue
        exists = (
            db.query(Order.id)
            .filter(Order.order_id == oid, Order.is_deleted.is_(False))
            .first()
        )
        if not exists:
            used.add(oid)
            return oid
    raise RuntimeError("Could not generate a unique order_id")


def seed_orders(count: int, dry_run: bool) -> int:
    db = SessionLocal()
    try:
        customers = (
            db.query(Location)
            .filter(
                Location.is_deleted.is_(False),
                Location.location_type == LocationType.CUSTOMER,
            )
            .all()
        )
        if not customers:
            print("ERROR: no active customers found. Create customers first.", file=sys.stderr)
            return 1

        print(f"Database: {engine.url}")
        print(f"Found {len(customers)} customers. Creating {count} dummy orders...")
        used_ids: set[str] = set()
        created = 0
        today = date.today()

        for i in range(count):
            customer = random.choice(customers)
            order_id = _unique_order_id(db, used_ids)
            tw_start, tw_end = random.choice(TIME_WINDOWS)
            order = Order(
                order_id=order_id,
                location_id=customer.id,
                po_value=round(random.uniform(5000, 250000), 2),
                volume=round(random.uniform(0.5, 15.0), 2),
                po_date=today - timedelta(days=random.randint(0, 14)),
                status=OrderStatus.PENDING,
                time_window_start=tw_start,
                time_window_end=tw_end,
                priority=random.choice(PRIORITIES),
            )
            if dry_run:
                if i < 5:
                    print(
                        f"  [dry-run] {order_id} -> {customer.location_code} "
                        f"({customer.location_name}) priority={order.priority.value}"
                    )
            else:
                db.add(order)
                created += 1
                if created % 50 == 0:
                    db.commit()
                    print(f"  committed {created}/{count}")

        if dry_run:
            print(f"Dry run complete. Would create {count} orders.")
            return 0

        db.commit()
        print(f"Done. Created {created} pending orders.")
        return 0
    except Exception as e:
        db.rollback()
        print(f"ERROR - rolled back: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed random dummy orders from customers")
    parser.add_argument("--count", type=int, default=200, help="Number of orders (default 200)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if args.count < 1:
        print("ERROR: --count must be >= 1", file=sys.stderr)
        sys.exit(1)

    sys.exit(seed_orders(args.count, args.dry_run))


if __name__ == "__main__":
    main()
