"""Matrix persistence helpers."""

from sqlalchemy.orm import Session

from src.infrastructure.database import models
from src.matrix.manager import DistanceMatrixManager


def get_pending_shops(db: Session):
    return (
        db.query(models.GPSMaster)
        .filter(
            (models.GPSMaster.matrix_status == "to_update")
            | (models.GPSMaster.matrix_status == "to_create")
        )
        .order_by(models.GPSMaster.id)
        .all()
    )


def get_stats(db: Session) -> dict:
    return DistanceMatrixManager(db).get_matrix_statistics()


def sync_pending(db: Session, max_workers: int = 10) -> int:
    """Process pending matrix updates. Returns calculation count (or 0)."""
    manager = DistanceMatrixManager(db, max_workers=max_workers)
    result = manager.process_pending_updates()
    return result or 0
