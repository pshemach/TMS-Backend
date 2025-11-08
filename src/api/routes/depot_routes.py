from fastapi import APIRouter, status,HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from src.database.repository import depot_curd
from .. import schemas
from src.database import database, models

get_db = database.get_db

router = APIRouter(prefix='/master', tags=['depot'])

def _enrich(depot: models.GPSMaster) -> schemas.DepotResponse:
    return schemas.DepotResponse(
        id=depot.id,
        depot_code=depot.shop_code,
        location=depot.location,
        address=depot.address,
        district=depot.district,
        latitude=depot.latitude,
        longitude=depot.longitude,
        matrix_status=depot.matrix_status
    )

@router.get('/depot', status_code=status.HTTP_200_OK, response_model=List[schemas.DepotResponse])
def get_all_depots(db: Session=Depends(get_db)):
    try:
        depots = depot_curd.get_all(db)
        return [_enrich(depot)  for depot in depots]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/depot/{id}', status_code=status.HTTP_200_OK, response_model=schemas.DepotResponse)
def get_depot(id: int, db: Session=Depends(get_db)):
    try:
        depot = depot_curd.get_depot(id, db)
        if not depot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Depot with id {id} not found")
        return _enrich(depot)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/depot', status_code=status.HTTP_201_CREATED, response_model=schemas.DepotResponse)
def create_depot(request: schemas.DepotRequest, db: Session=Depends(get_db)):
    try:
        new_depot = depot_curd.create(request, db)
        return _enrich(new_depot)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete('/depot/{id}', status_code=status.HTTP_200_OK)
def delete_depot(id: int, db: Session=Depends(get_db)):
    try:
        msg = depot_curd.delete(id, db)
        if not msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Depot with id {id} not found")
        return msg
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put('/depot/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.DepotResponse)
def update_depot(id: int, request: schemas.DepotRequest, db: Session=Depends(get_db)):
    try:
        depot = depot_curd.update(id, request, db)
        if not depot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Depot with id {id} not found")
        return _enrich(depot)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    