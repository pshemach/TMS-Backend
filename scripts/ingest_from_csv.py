"""Bulk-loads shop + distance/duration matrix data from CSV files directly into
the TMS SQLite database, bypassing DistanceMatrixManager.process_pending_updates()
(which hits the OSRM API for every pair and is slow).
 
Expected files (adjust paths in CONFIG below if different):
    data/csv/master_gps.csv
    data/csv/osrm_distance_matrix.csv
    data/csv/osrm_duration_matrix.csv
 
The matrix CSVs can be in either format and this script auto-detects which:
  WIDE  (grid):  header row = ["shop_code", <code2>, <code3>, ...]
                 each data row = [<code1>, val, val, ...]
  LONG  (list):  header row has columns like shop_code_1/shop_code_2/value
                 (aliases are matched, see CONFIG)
 
USAGE
-----
    # 1. ALWAYS do a dry run first and read the printed preview carefully
    python bulk_load_from_csv.py --dry-run
 
    # 2. If the preview looks right, actually write to the DB
    python bulk_load_from_csv.py
 
    # Optional: point at a different folder
    python bulk_load_from_csv.py --csv-dir "C:\\path\\to\\csv" --dry-run
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# CONFIG - adjust if your project layout / CSV headers differ
# ---------------------------------------------------------------------------
 
# Import your existing session + models (adjust the import path if needed)
from src.database.database import get_db
from src.database.models import GPSMaster, MatrixMaster
 
DEFAULT_CSV_DIR = Path("data/csv")
MASTER_GPS_FILE = "master_gps.csv"
DISTANCE_FILE = "osrm_distance_matrix.csv"
DURATION_FILE = "osrm_duration_matrix.csv"
 
# Accepted aliases (lowercased) for master_gps.csv columns
GPS_COLUMN_ALIASES = {
    "shop_code": ["shop_code", "code", "shopcode"],
    "location": ["location", "loc"],
    "address": ["address", "addr"],
    "brand": ["brand"],
    "district": ["district"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng"],
}
 
# Accepted aliases for LONG-format matrix CSVs
LONG_COL_ALIASES = {
    "code1": ["shop_code_1", "from", "source", "origin", "code1", "shop1"],
    "code2": ["shop_code_2", "to", "target", "destination", "code2", "shop2"],
    "value": ["distance_km", "distance", "time_minutes", "duration", "value", "km", "minutes"],
}
 
BATCH_COMMIT_EVERY = 200  # commit periodically instead of one giant transaction
 
# ---------------------------------------------------------------------------

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
        if idx is None:
            raise ValueError(
                f"Could not find a column for '{field}' in master_gps.csv "
                f"(looked for any of {aliases}). Actual headers: {header_norm}"
            )
        resolved[field] = idx
    return resolved
 
 
def load_master_gps(path):
    """Returns list of dicts: shop_code, location, address, brand, district, latitude, longitude"""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        header_norm = normalize_header(header)
        cols = resolve_gps_columns(header_norm)
 
        shops = []
        for row in reader:
            if not row or not row[cols["shop_code"]].strip():
                continue
            shops.append({
                "shop_code": row[cols["shop_code"]].strip(),
                "location": row[cols["location"]].strip(),
                "address": row[cols["address"]].strip(),
                "brand": row[cols["brand"]].strip(),
                "district": row[cols["district"]].strip(),
                "latitude": float(row[cols["latitude"]]),
                "longitude": float(row[cols["longitude"]]),
            })
        return shops
 
 
def load_matrix_csv(path):
    """
    Auto-detects wide vs long format.
    Returns dict[(shop_code_1, shop_code_2)] = float_value
    (unordered pair key, i.e. only one direction stored, using sorted tuple)
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
 
    if not rows:
        raise ValueError(f"{path} is empty")
 
    header = rows[0]
    header_norm = normalize_header(header)
    data_rows = rows[1:]
 
    # --- Try WIDE format detection ---
    # Wide format: first column is a row-label column, remaining header cells
    # are shop codes, and each data row's first cell is also a shop code.
    row_labels = [r[0].strip() for r in data_rows if r]
    col_labels = [h.strip() for h in header[1:]]
 
    looks_wide = (
        len(header) > 2
        and len(row_labels) > 0
        and len(set(row_labels) & set(col_labels)) > max(1, len(col_labels) // 2)
    )
 
    result = {}
 
    if looks_wide:
        print(f"  [detected] WIDE matrix format in {path.name} "
              f"({len(row_labels)} rows x {len(col_labels)} cols)")
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
                key = tuple(sorted((code1, code2)))
                result[key] = val
        return result
 
    # --- Fall back to LONG format ---
    idx_c1 = find_col(header_norm, LONG_COL_ALIASES["code1"])
    idx_c2 = find_col(header_norm, LONG_COL_ALIASES["code2"])
    idx_val = find_col(header_norm, LONG_COL_ALIASES["value"])
 
    if idx_c1 is None or idx_c2 is None or idx_val is None:
        raise ValueError(
            f"Could not detect matrix format for {path}. "
            f"Headers found: {header}. Neither a WIDE grid nor a recognizable "
            f"LONG format (code1/code2/value columns) was matched. "
            f"Adjust LONG_COL_ALIASES in this script or check the file."
        )
 
    print(f"  [detected] LONG matrix format in {path.name} "
          f"(cols: {header[idx_c1]!r}, {header[idx_c2]!r}, {header[idx_val]!r})")
 
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
        key = tuple(sorted((code1, code2)))
        result[key] = val
 
    return result
 
 
def upsert_shops(db, shops):
    """Insert/update GPSMaster rows by shop_code. Returns dict[shop_code] -> GPSMaster row."""
    code_to_shop = {}
    created, updated, unchanged = 0, 0, 0
 
    for s in shops:
        existing = db.query(GPSMaster).filter(GPSMaster.shop_code == s["shop_code"]).first()
        if existing:
            changed = (
                existing.latitude != s["latitude"]
                or existing.longitude != s["longitude"]
                or existing.location != s["location"]
                or existing.address != s["address"]
                or existing.brand != s["brand"]
                or existing.district != s["district"]
            )
            if changed:
                existing.location = s["location"]
                existing.address = s["address"]
                existing.brand = s["brand"]
                existing.district = s["district"]
                existing.latitude = s["latitude"]
                existing.longitude = s["longitude"]
                updated += 1
            else:
                unchanged += 1
            code_to_shop[s["shop_code"]] = existing
        else:
            new_shop = GPSMaster(
                shop_code=s["shop_code"],
                location=s["location"],
                address=s["address"],
                brand=s["brand"],
                district=s["district"],
                latitude=s["latitude"],
                longitude=s["longitude"],
                matrix_status="to_create",
            )
            db.add(new_shop)
            created += 1
            code_to_shop[s["shop_code"]] = new_shop
 
    db.flush()  # assigns IDs to newly created shops without committing
    print(f"  Shops -> created: {created}, updated: {updated}, unchanged: {unchanged}")
    return code_to_shop
 
 
def upsert_matrix(db, code_to_shop, distances, durations, dry_run):
    """
    distances / durations: dict[(code1, code2)] -> float
    Merges on the pair key; a pair needs BOTH a distance and duration to be written.
    """
    pairs = set(distances.keys()) & set(durations.keys())
    missing_distance = set(durations.keys()) - set(distances.keys())
    missing_duration = set(distances.keys()) - set(durations.keys())
 
    if missing_distance:
        print(f"  [warn] {len(missing_distance)} pairs have duration but no distance - skipped")
    if missing_duration:
        print(f"  [warn] {len(missing_duration)} pairs have distance but no duration - skipped")
 
    created, updated, skipped_unknown_shop = 0, 0, 0
    touched_shop_codes = set()
 
    for i, (code1, code2) in enumerate(pairs, start=1):
        shop1 = code_to_shop.get(code1)
        shop2 = code_to_shop.get(code2)
        if not shop1 or not shop2:
            skipped_unknown_shop += 1
            continue
 
        sid1, scode1, sid2, scode2 = (
            (shop1.id, code1, shop2.id, code2)
            if shop1.id < shop2.id
            else (shop2.id, code2, shop1.id, code1)
        )
        # keep value orientation consistent with id ordering (values are symmetric anyway)
        dist_val = distances[(code1, code2)]
        dur_val = durations[(code1, code2)]
 
        touched_shop_codes.add(code1)
        touched_shop_codes.add(code2)
 
        if dry_run:
            continue
 
        existing = db.query(MatrixMaster).filter(
            MatrixMaster.shop_id_1 == sid1,
            MatrixMaster.shop_id_2 == sid2,
        ).first()
 
        if existing:
            existing.distance_km = dist_val
            existing.time_minutes = dur_val
            existing.last_calculated = datetime.utcnow()
            updated += 1
        else:
            db.add(MatrixMaster(
                shop_id_1=sid1,
                shop_id_2=sid2,
                shop_code_1=scode1,
                shop_code_2=scode2,
                distance_km=dist_val,
                time_minutes=dur_val,
                coords=None,  # OSRM table/matrix CSVs don't carry route geometry
                last_calculated=datetime.utcnow(),
            ))
            created += 1
 
        if not dry_run and (created + updated) % BATCH_COMMIT_EVERY == 0:
            db.commit()
 
    print(f"  Matrix rows -> matched pairs: {len(pairs)}, "
          f"created: {created}, updated: {updated}, "
          f"skipped (shop not in master_gps.csv): {skipped_unknown_shop}")
 
    return touched_shop_codes
 
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    parser.add_argument("--dry-run", action="store_true",
                         help="Parse and preview everything, but don't write to the DB")
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
    shops = load_master_gps(gps_path)
    print(f"  Parsed {len(shops)} shop rows")
    if shops:
        print(f"  Sample row: {shops[0]}")
 
    print(f"\nReading {dist_path.name} ...")
    distances = load_matrix_csv(dist_path)
    print(f"  Parsed {len(distances)} distance pairs")
 
    print(f"\nReading {dur_path.name} ...")
    durations = load_matrix_csv(dur_path)
    print(f"  Parsed {len(durations)} duration pairs")
 
    if args.dry_run:
        sample_pairs = list((set(distances) & set(durations)))[:5]
        print("\nSample merged pairs (code1, code2) -> (distance_km, time_minutes):")
        for k in sample_pairs:
            print(f"  {k} -> ({distances[k]}, {durations[k]})")
        print("\nNo database writes performed (dry run). "
              "Re-run without --dry-run once this looks correct.")
        return
 
    db_gen = get_db()
    db = next(db_gen)
    try:
        print("\nUpserting shops into GPSMaster ...")
        code_to_shop = upsert_shops(db, shops)
        db.commit()
 
        print("\nUpserting distances/durations into MatrixMaster ...")
        touched_codes = upsert_matrix(db, code_to_shop, distances, durations, dry_run=False)
        db.commit()
 
        print("\nMarking touched shops as matrix_status='updated' ...")
        count = 0
        for code in touched_codes:
            shop = code_to_shop.get(code)
            if shop and shop.matrix_status != "updated":
                shop.matrix_status = "updated"
                count += 1
        db.commit()
        print(f"  Updated status for {count} shops")
 
        print("\nDone.")
    except Exception as e:
        db.rollback()
        print(f"\nERROR - rolled back all changes: {e}", file=sys.stderr)
        raise
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
 
 
if __name__ == "__main__":
    main()