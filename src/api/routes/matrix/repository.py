"""Matrix persistence helpers."""

from sqlalchemy.orm import Session

from src.infrastructure.database import models
from src.matrix.manager import DistanceMatrixManager


def get_pending_locations(db: Session):
    return (
        db.query(models.Location)
        .filter(
            models.Location.is_deleted.is_(False),
            models.Location.matrix_status.in_(
                [models.MatrixStatus.TO_UPDATE, models.MatrixStatus.TO_CREATE]
            ),
        )
        .order_by(models.Location.id)
        .all()
    )


get_pending_shops = get_pending_locations


def get_stats(db: Session) -> dict:
    return DistanceMatrixManager(db).get_matrix_statistics()


def sync_pending(db: Session, max_workers: int = 10) -> int:
    manager = DistanceMatrixManager(db, max_workers=max_workers)
    result = manager.process_pending_updates()
    return result or 0
