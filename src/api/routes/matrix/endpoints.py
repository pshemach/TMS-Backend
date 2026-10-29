"""Matrix sync and status endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.matrix import repository, schemas
from src.infrastructure.database.session import SessionLocal
from src.infrastructure.logging import logging

router = APIRouter(prefix="/matrix", tags=["matrix"])

def _run_matrix_sync_task(max_workers: int = 10) -> None:
    """Background worker — opens its own DB session."""
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
    """Return current distance-matrix coverage statistics."""
    return repository.get_stats(db)

@router.get("/pending", response_model=schemas.PendingShopsResponse)
def matrix_pending(db: Session = Depends(get_db)):
    """List shops waiting for matrix create/update."""
    shops = repository.get_pending_shops(db)
    return schemas.PendingShopsResponse(
        count=len(shops),
        shops=[
            schemas.PendingShopItem(
                id=s.id,
                shop_code=s.shop_code,
                location=s.location,
                brand=s.brand,
                matrix_status=s.matrix_status,
            )
            for s in shops
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
    """
    Sync pending shops into the distance/duration matrix (background).

    Processes GPS rows with matrix_status `to_create` or `to_update`
    via OSRM, then marks them `updated`.
    """
    pending = repository.get_pending_shops(db)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending shops to sync (matrix_status to_create/to_update)",
        )

    background_tasks.add_task(_run_matrix_sync_task, request.max_workers or 10)
    return schemas.MatrixSyncResponse(
        message="Matrix sync started",
        pending_before=len(pending),
    )
