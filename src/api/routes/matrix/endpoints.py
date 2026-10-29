"""Matrix sync and status endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.matrix import repository, schemas
from src.infrastructure.database.session import SessionLocal
from src.infrastructure.logging import logging

router = APIRouter(prefix="/matrix", tags=["matrix"])


def _run_matrix_sync_task(max_workers: int = 10) -> None:
    db = SessionLocal()
    try:
        logging.info(f"Matrix sync started (workers={max_workers})")
        calculations = repository.sync_pending(db, max_workers=max_workers)
        logging.info(f"Matrix sync finished — calculations={calculations}")
    except Exception as exc:
        logging.error(f"Matrix sync failed: {exc}")
    finally:
        db.close()


@router.get("/stats", response_model=schemas.MatrixStatsResponse)
def matrix_stats(db: Session = Depends(get_db)):
    return repository.get_stats(db)


@router.get("/pending", response_model=schemas.PendingLocationsResponse)
def matrix_pending(db: Session = Depends(get_db)):
    locations = repository.get_pending_locations(db)
    return schemas.PendingLocationsResponse(
        count=len(locations),
        locations=[
            schemas.PendingLocationItem(
                id=s.id,
                location_code=s.location_code,
                location_name=s.location_name,
                brand=s.brand,
                location_type=s.location_type.value
                if hasattr(s.location_type, "value")
                else str(s.location_type),
                matrix_status=s.matrix_status.value
                if hasattr(s.matrix_status, "value")
                else str(s.matrix_status),
            )
            for s in locations
        ],
    )


@router.post(
    "/sync",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=schemas.MatrixSyncResponse,
)
def sync_matrix(
    background_tasks: BackgroundTasks,
    request: schemas.MatrixSyncRequest = schemas.MatrixSyncRequest(),
    db: Session = Depends(get_db),
):
    pending = repository.get_pending_locations(db)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending locations to sync (matrix_status to_create/to_update)",
        )

    background_tasks.add_task(_run_matrix_sync_task, request.max_workers or 10)
    return schemas.MatrixSyncResponse(
        message="Matrix sync started",
        pending_before=len(pending),
    )
