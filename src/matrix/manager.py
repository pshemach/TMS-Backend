"""Distance / duration matrix manager (Location pairs)."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.infrastructure.database.models import DistanceMatrix, Location, MatrixStatus
from src.infrastructure.logging import logging
from src.matrix.osrm import get_osrm_data


class DistanceMatrixManager:
    """Manager class for distance matrix operations with threading support."""

    def __init__(self, db_session: Session, max_workers: int = 10):
        self.db = db_session
        self.max_workers = max_workers
        self._lock = threading.Lock()

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> Tuple[float, float, object]:
        coords, distance, duration = get_osrm_data((lat1, lon1), (lat2, lon2))
        return distance, duration, coords

    def _active_locations(self):
        return self.db.query(Location).filter(Location.is_deleted.is_(False))

    def process_pending_updates(self):
        pending = (
            self._active_locations()
            .filter(
                Location.matrix_status.in_(
                    [MatrixStatus.TO_UPDATE, MatrixStatus.TO_CREATE]
                )
            )
            .all()
        )

        if not pending:
            logging.info("No pending updates found.")
            return 0

        to_update = (
            self._active_locations()
            .filter(Location.matrix_status == MatrixStatus.TO_UPDATE)
            .all()
        )
        for loc in to_update:
            self._delete_location_distances(loc.id, self.db)

        existing = (
            self._active_locations()
            .filter(Location.matrix_status == MatrixStatus.UPDATED)
            .all()
        )

        logging.info(
            f"Processing {len(pending)} pending locations with {len(existing)} existing..."
        )

        total_calculations = 0
        pending_ids = [loc.id for loc in pending]

        for location_id in pending_ids:
            try:
                pending_loc = (
                    self._active_locations()
                    .filter(Location.id == location_id)
                    .first()
                )
                if not pending_loc:
                    continue

                logging.info(
                    f"Processing location: {pending_loc.location_code} (ID: {pending_loc.id})"
                )

                existing = (
                    self._active_locations()
                    .filter(Location.matrix_status == MatrixStatus.UPDATED)
                    .all()
                )

                distances_added = self._add_location_to_matrix_threaded(
                    pending_loc, existing
                )

                other_pending_ids = [sid for sid in pending_ids if sid > location_id]
                if other_pending_ids:
                    other_pending = (
                        self._active_locations()
                        .filter(Location.id.in_(other_pending_ids))
                        .all()
                    )
                    if other_pending:
                        pending_distances = self._calculate_distances_threaded(
                            pending_loc, other_pending
                        )
                        distances_added += len(pending_distances)

                matrix_rows = (
                    self.db.query(DistanceMatrix)
                    .filter(
                        (DistanceMatrix.location_id_1 == location_id)
                        | (DistanceMatrix.location_id_2 == location_id)
                    )
                    .all()
                )
                if len(matrix_rows) > 0:
                    pending_loc.matrix_status = MatrixStatus.UPDATED
                    total_calculations += distances_added

                try:
                    self.db.commit()
                    self.db.expire_all()
                except Exception as commit_error:
                    logging.error(f"Error committing to database: {commit_error}")
                    self.db.rollback()
                    self.db.expire_all()
                    continue

            except Exception as e:
                logging.error(f"Error processing location ID {location_id}: {e}")
                try:
                    self.db.rollback()
                    self.db.expire_all()
                except Exception:
                    pass
                continue

        return total_calculations

    def _delete_location_distances(self, location_id: int, db: Session) -> None:
        db.query(DistanceMatrix).filter(
            (DistanceMatrix.location_id_1 == location_id)
            | (DistanceMatrix.location_id_2 == location_id)
        ).delete(synchronize_session=False)
        db.commit()

    def _add_location_to_matrix_threaded(
        self, new_loc: Location, existing: List[Location]
    ) -> int:
        if not existing:
            return 0
        results = self._calculate_distances_threaded(new_loc, existing)
        return len(results)

    def _calculate_distances_threaded(
        self, source: Location, targets: List[Location]
    ) -> List[Dict]:
        distance_results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._calculate_single_distance, source, target): target
                for target in targets
            }
            for future in as_completed(future_map):
                target = future_map[future]
                try:
                    result = future.result()
                    if result:
                        distance_results.append(result)
                except Exception as e:
                    logging.error(
                        f"Error calculating distance to {target.location_code}: {e}"
                    )

        for result in distance_results:
            self._save_distance_to_db(result)
        return distance_results

    def _calculate_single_distance(self, loc1: Location, loc2: Location) -> Optional[Dict]:
        try:
            distance, time, coords = self.calculate_distance(
                loc1.latitude, loc1.longitude, loc2.latitude, loc2.longitude
            )
            return {
                "location_id_1": loc1.id,
                "location_id_2": loc2.id,
                "location_code_1": loc1.location_code,
                "location_code_2": loc2.location_code,
                "distance_km": distance,
                "time_minutes": time,
                "coords": coords,
            }
        except Exception as e:
            logging.error(
                f"Error calculating {loc1.location_code} → {loc2.location_code}: {e}"
            )
            return None

    def _save_distance_to_db(self, distance_data: Dict) -> None:
        try:
            sid1 = min(distance_data["location_id_1"], distance_data["location_id_2"])
            sid2 = max(distance_data["location_id_1"], distance_data["location_id_2"])

            if distance_data["location_id_1"] == sid1:
                scode1 = distance_data["location_code_1"]
                scode2 = distance_data["location_code_2"]
                coords = distance_data["coords"]
            else:
                scode1 = distance_data["location_code_2"]
                scode2 = distance_data["location_code_1"]
                coords = (
                    distance_data["coords"][::-1]
                    if distance_data["coords"]
                    else None
                )

            existing = (
                self.db.query(DistanceMatrix)
                .filter(
                    DistanceMatrix.location_id_1 == sid1,
                    DistanceMatrix.location_id_2 == sid2,
                )
                .first()
            )

            if existing:
                existing.distance_km = distance_data["distance_km"]
                existing.time_minutes = distance_data["time_minutes"]
                existing.coords = json.dumps(coords) if coords else None
                existing.last_calculated = datetime.utcnow()
                self.db.commit()
            else:
                self.db.add(
                    DistanceMatrix(
                        location_id_1=sid1,
                        location_id_2=sid2,
                        location_code_1=scode1,
                        location_code_2=scode2,
                        distance_km=distance_data["distance_km"],
                        time_minutes=distance_data["time_minutes"],
                        coords=json.dumps(coords) if coords else None,
                        last_calculated=datetime.utcnow(),
                    )
                )
                self.db.commit()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            logging.error(f"Error saving distance: {e}")

    def get_distance(
        self, location_id_1: int, location_id_2: int
    ) -> Tuple[Optional[float], Optional[float]]:
        if location_id_1 == location_id_2:
            return 0.0, 0.0

        sid1 = min(location_id_1, location_id_2)
        sid2 = max(location_id_1, location_id_2)
        result = (
            self.db.query(DistanceMatrix)
            .filter(
                DistanceMatrix.location_id_1 == sid1,
                DistanceMatrix.location_id_2 == sid2,
            )
            .first()
        )
        if result:
            return result.distance_km, result.time_minutes
        return None, None

    def get_matrix_for_shops(self, location_ids: List[int]) -> Dict[Tuple[int, int], Dict]:
        """Kept name for VRP callers; operates on location IDs."""
        distance_dict = {}
        for location_id in location_ids:
            distance_dict[(location_id, location_id)] = {"distance": 0.0, "time": 0.0}

        for i, id1 in enumerate(location_ids):
            for id2 in location_ids[i + 1 :]:
                distance, time = self.get_distance(id1, id2)
                if distance is not None:
                    distance_dict[(id1, id2)] = {"distance": distance, "time": time}
                    distance_dict[(id2, id1)] = {"distance": distance, "time": time}
        return distance_dict

    def get_distance_matrix_as_array(self, location_ids: List[int]) -> List[List[float]]:
        n = len(location_ids)
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        distance_dict = self.get_matrix_for_shops(location_ids)
        for i, id1 in enumerate(location_ids):
            for j, id2 in enumerate(location_ids):
                if (id1, id2) in distance_dict:
                    matrix[i][j] = distance_dict[(id1, id2)]["distance"]
        return matrix

    def get_time_matrix_as_array(self, location_ids: List[int]) -> List[List[float]]:
        n = len(location_ids)
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        distance_dict = self.get_matrix_for_shops(location_ids)
        for i, id1 in enumerate(location_ids):
            for j, id2 in enumerate(location_ids):
                if (id1, id2) in distance_dict:
                    matrix[i][j] = distance_dict[(id1, id2)]["time"]
        return matrix

    def get_matrix_statistics(self) -> Dict:
        total = (
            self._active_locations()
            .filter(Location.matrix_status == MatrixStatus.UPDATED)
            .count()
        )
        pending = (
            self._active_locations()
            .filter(
                Location.matrix_status.in_(
                    [MatrixStatus.TO_UPDATE, MatrixStatus.TO_CREATE]
                )
            )
            .count()
        )
        total_distances = self.db.query(DistanceMatrix).count()
        expected = (total * (total - 1)) / 2 if total > 0 else 0
        return {
            "total_locations_in_matrix": total,
            "pending_updates": pending,
            "total_distances_stored": total_distances,
            "expected_distances": int(expected),
            "matrix_completeness": (
                f"{(total_distances / expected * 100):.1f}%" if expected > 0 else "N/A"
            ),
        }
