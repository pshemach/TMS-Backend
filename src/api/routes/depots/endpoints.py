from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.depots import repository as depot_repo
from src.api.routes.depots import schemas

router = APIRouter(prefix="/location", tags=["location"])


def _enrich(depot) -> schemas.DepotResponse:
    return schemas.DepotResponse(
        id=depot.id,
        location_code=depot.location_code,
        location_name=depot.location_name,
        address=depot.address,
        district=depot.district or "",
        latitude=depot.latitude,
        longitude=depot.longitude,
        location_type=depot.location_type.value
        if hasattr(depot.location_type, "value")
        else str(depot.location_type),
        matrix_status=depot.matrix_status.value
        if hasattr(depot.matrix_status, "value")
        else str(depot.matrix_status),
    )


@router.get("/depot", status_code=status.HTTP_200_OK, response_model=List[schemas.DepotResponse])
def get_all_depots(db: Session = Depends(get_db)):
    try:
        return [_enrich(d) for d in depot_repo.get_all(db)]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/depot/{id}", status_code=status.HTTP_200_OK, response_model=schemas.DepotResponse)
def get_depot(id: int, db: Session = Depends(get_db)):
    try:
        depot = depot_repo.get_depot(id, db)
        if not depot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Depot with id {id} not found",
            )
        return _enrich(depot)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/depot", status_code=status.HTTP_201_CREATED, response_model=schemas.DepotResponse)
def create_depot(request: schemas.DepotRequest, db: Session = Depends(get_db)):
    try:
        return _enrich(depot_repo.create(request, db))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/depot/{id}", status_code=status.HTTP_200_OK)
def delete_depot(id: int, db: Session = Depends(get_db)):
    try:
        msg = depot_repo.delete(id, db)
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Depot with id {id} not found",
            )
        return msg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/depot/{id}", status_code=status.HTTP_202_ACCEPTED, response_model=schemas.DepotResponse)
def update_depot(id: int, request: schemas.DepotRequest, db: Session = Depends(get_db)):
    try:
        depot = depot_repo.update(id, request, db)
        if not depot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Depot with id {id} not found",
            )
        return _enrich(depot)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
