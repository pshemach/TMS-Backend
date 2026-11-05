"""Bulk-load location + distance/duration matrix data from CSV into the DB.

Expected files (adjust paths via --csv-dir):
    data/csv/master_gps.csv
    data/csv/osrm_distance_matrix.csv
    data/csv/osrm_duration_matrix.csv

CSV may include location_type / type. If missing and brand is 'depot',
row is typed as depot (ingest-only compat); app code never uses brand for type.

Usage:
    python scripts/ingest_from_csv.py --dry-run
    python scripts/ingest_from_csv.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.database.models import (
    DistanceMatrix,
    Location,
    LocationType,
    MatrixStatus,
)
from src.infrastructure.database.session import SessionLocal

DEFAULT_CSV_DIR = Path("data/csv")
MASTER_GPS_FILE = "master_gps.csv"
DISTANCE_FILE = "osrm_distance_matrix.csv"
DURATION_FILE = "osrm_duration_matrix.csv"

GPS_COLUMN_ALIASES = {
    "location_code": [
        "location_code",
        "shop_code",
        "code",
        "shopcode",
        "customer_code",
        "depot_code",
    ],
    "location_name": ["location_name", "location", "loc", "name"],
    "address": ["address", "addr"],
    "brand": ["brand"],
    "district": ["district"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng"],
}

OPTIONAL_TYPE_ALIASES = ["location_type", "type", "loctype"]

LONG_COL_ALIASES = {
    "code1": ["location_code_1", "shop_code_1", "from", "source", "origin", "code1"],
    "code2": ["location_code_2", "shop_code_2", "to", "target", "destination", "code2"],
    "value": [
        "distance_km",
        "distance",
        "time_minutes",
        "duration",
        "value",
        "km",
        "minutes",
    ],
}

BATCH_COMMIT_EVERY = 200


def normalize_header(row):
    return [c.strip().lower() for c in row]


def find_col(header_norm, aliases):
    for alias in aliases:
        if alias in header_norm:
            return header_norm.index(alias)
    return None


def resolve_gps_columns(header_norm):
    resolved = {}
    for field, aliases in GPS_COLUMN_ALIASES.items():
        idx = find_col(header_norm, aliases)
        if idx is None and field == "brand":
            resolved[field] = None
            continue
        if idx is None:
            raise ValueError(
                f"Could not find a column for '{field}' in {MASTER_GPS_FILE} "
                f"(looked for any of {aliases}). Actual headers: {header_norm}"
            )
        resolved[field] = idx
    resolved["location_type"] = find_col(header_norm, OPTIONAL_TYPE_ALIASES)
    return resolved


def _resolve_type(raw_type: str | None, brand: str | None) -> LocationType:
    if raw_type:
        value = raw_type.strip().lower()
        if value in {"depot", "depots"}:
            return LocationType.DEPOT
        if value in {"customer", "customers", "shop", "shops"}:
            return LocationType.CUSTOMER
    if brand and brand.strip().lower() == "depot":
        return LocationType.DEPOT
    return LocationType.CUSTOMER


def load_locations(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        header_norm = normalize_header(header)
        cols = resolve_gps_columns(header_norm)

        locations = []
        for row in reader:
            if not row or not row[cols["location_code"]].strip():
                continue
            brand = (
                row[cols["brand"]].strip()
                if cols["brand"] is not None and cols["brand"] < len(row)
                else None
            )
            raw_type = (
                row[cols["location_type"]].strip()
                if cols["location_type"] is not None and cols["location_type"] < len(row)
                else None
            )
            locations.append(
                {
                    "location_code": row[cols["location_code"]].strip(),
                    "location_name": row[cols["location_name"]].strip(),
                    "address": row[cols["address"]].strip(),
                    "brand": brand,
                    "district": row[cols["district"]].strip(),
                    "latitude": float(row[cols["latitude"]]),
                    "longitude": float(row[cols["longitude"]]),
                    "location_type": _resolve_type(raw_type, brand),
                }
            )
        return locations


def load_matrix_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"{path} is empty")

    header = rows[0]
    header_norm = normalize_header(header)
    data_rows = rows[1:]

    row_labels = [r[0].strip() for r in data_rows if r]
    col_labels = [h.strip() for h in header[1:]]

    looks_wide = (
        len(header) > 2
        and len(row_labels) > 0
        and len(set(row_labels) & set(col_labels)) > max(1, len(col_labels) // 2)
    )

    result = {}
    if looks_wide:
        print(
            f"  [detected] WIDE matrix format in {path.name} "
            f"({len(row_labels)} rows x {len(col_labels)} cols)"
        )
        for r in data_rows:
            if not r:
                continue
            code1 = r[0].strip()
            for j, code2 in enumerate(col_labels, start=1):
                if j >= len(r):
                    continue
                raw = r[j].strip()
                if raw == "" or code1 == code2:
                    continue
                try:
                    val = float(raw)
                except ValueError:
                    continue
                result[tuple(sorted((code1, code2)))] = val
        return result

    idx_c1 = find_col(header_norm, LONG_COL_ALIASES["code1"])
    idx_c2 = find_col(header_norm, LONG_COL_ALIASES["code2"])
    idx_val = find_col(header_norm, LONG_COL_ALIASES["value"])
    if idx_c1 is None or idx_c2 is None or idx_val is None:
        raise ValueError(f"Could not detect matrix format for {path}. Headers: {header}")

    print(
        f"  [detected] LONG matrix format in {path.name} "
        f"(cols: {header[idx_c1]!r}, {header[idx_c2]!r}, {header[idx_val]!r})"
    )
    for r in data_rows:
        if not r:
            continue
        code1 = r[idx_c1].strip()
        code2 = r[idx_c2].strip()
        raw = r[idx_val].strip()
        if not code1 or not code2 or raw == "" or code1 == code2:
            continue
        try:
            val = float(raw)
        except ValueError:
            continue
        result[tuple(sorted((code1, code2)))] = val
    return result


def upsert_locations(db, locations):
    code_to_location = {}
    created, updated, unchanged = 0, 0, 0

    for row in locations:
        existing = (
            db.query(Location)
            .filter(
                Location.location_code == row["location_code"],
                Location.is_deleted.is_(False),
            )
            .first()
        )
        if existing:
            changed = (
                existing.latitude != row["latitude"]
                or existing.longitude != row["longitude"]
                or existing.location_name != row["location_name"]
                or existing.address != row["address"]
                or existing.brand != row["brand"]
                or existing.district != row["district"]
                or existing.location_type != row["location_type"]
            )
            if changed:
                existing.location_name = row["location_name"]
                existing.address = row["address"]
                existing.brand = row["brand"]
                existing.district = row["district"]
                existing.latitude = row["latitude"]
                existing.longitude = row["longitude"]
                existing.location_type = row["location_type"]
                updated += 1
            else:
                unchanged += 1
            code_to_location[row["location_code"]] = existing
        else:
            new_row = Location(
                location_code=row["location_code"],
                location_name=row["location_name"],
                address=row["address"],
                brand=row["brand"],
                district=row["district"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                location_type=row["location_type"],
                matrix_status=MatrixStatus.TO_CREATE,
            )
            db.add(new_row)
            created += 1
            code_to_location[row["location_code"]] = new_row

    db.flush()
    print(f"  Locations -> created: {created}, updated: {updated}, unchanged: {unchanged}")
    return code_to_location


def upsert_matrix(db, code_to_location, distances, durations, dry_run):
    pairs = set(distances.keys()) & set(durations.keys())
    created, updated, skipped_unknown = 0, 0, 0
    touched_codes = set()

    for code1, code2 in pairs:
        loc1 = code_to_location.get(code1)
        loc2 = code_to_location.get(code2)
        if not loc1 or not loc2:
            skipped_unknown += 1
            continue

        sid1, scode1, sid2, scode2 = (
            (loc1.id, code1, loc2.id, code2)
            if loc1.id < loc2.id
            else (loc2.id, code2, loc1.id, code1)
        )
        dist_val = distances[(code1, code2)]
        dur_val = durations[(code1, code2)]
        touched_codes.add(code1)
        touched_codes.add(code2)

        if dry_run:
            continue

        existing = (
            db.query(DistanceMatrix)
            .filter(
                DistanceMatrix.location_id_1 == sid1,
                DistanceMatrix.location_id_2 == sid2,
            )
            .first()
        )
        if existing:
            existing.distance_km = dist_val
            existing.time_minutes = dur_val
            existing.last_calculated = datetime.utcnow()
            updated += 1
        else:
            db.add(
                DistanceMatrix(
                    location_id_1=sid1,
                    location_id_2=sid2,
                    location_code_1=scode1,
                    location_code_2=scode2,
                    distance_km=dist_val,
                    time_minutes=dur_val,
                    coords=None,
                    last_calculated=datetime.utcnow(),
                )
            )
            created += 1

        if not dry_run and (created + updated) % BATCH_COMMIT_EVERY == 0:
            db.commit()

    print(
        f"  Matrix rows -> matched pairs: {len(pairs)}, "
        f"created: {created}, updated: {updated}, "
        f"skipped (unknown code): {skipped_unknown}"
    )
    return touched_codes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    gps_path = args.csv_dir / MASTER_GPS_FILE
    dist_path = args.csv_dir / DISTANCE_FILE
    dur_path = args.csv_dir / DURATION_FILE
    for p in (gps_path, dist_path, dur_path):
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"{'DRY RUN - ' if args.dry_run else ''}Loading CSVs from {args.csv_dir.resolve()}\n")

    print(f"Reading {gps_path.name} ...")
    locations = load_locations(gps_path)
    print(f"  Parsed {len(locations)} location rows")

    print(f"\nReading {dist_path.name} ...")
    distances = load_matrix_csv(dist_path)
    print(f"  Parsed {len(distances)} distance pairs")

    print(f"\nReading {dur_path.name} ...")
    durations = load_matrix_csv(dur_path)
    print(f"  Parsed {len(durations)} duration pairs")

    if args.dry_run:
        print("\nNo database writes performed (dry run).")
        return

    db = SessionLocal()
    try:
        print("\nUpserting locations ...")
        code_to_location = upsert_locations(db, locations)
        db.commit()

        print("\nUpserting matrix ...")
        touched = upsert_matrix(db, code_to_location, distances, durations, dry_run=False)
        db.commit()

        print("\nMarking touched locations as updated ...")
        count = 0
        for code in touched:
            loc = code_to_location.get(code)
            if loc and loc.matrix_status != MatrixStatus.UPDATED:
                loc.matrix_status = MatrixStatus.UPDATED
                count += 1
        db.commit()
        print(f"  Updated status for {count} locations")
        print("\nDone.")
    except Exception as e:
        db.rollback()
        print(f"\nERROR - rolled back: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
