from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from src.database.repository import fleet_operation
from ..schemas import FleetRequest
from src.database import database

get_db = database.get_db

fleet_router = APIRouter(
        prefix='/fleet',
    tags=['fleet']
)

@fleet_router.get('/', status_code=status.HTTP_200_OK)
def get_all_fleet(db: Session=Depends(get_db)):
    fleets = fleet_operation.all_fleets(db)
    return fleets

@fleet_router.get('/{id}', status_code=status.HTTP_200_OK)
def get_fleet(id: int, db: Session=Depends(get_db)):
    fleet = fleet_operation.get_fleet(id=id, db=db)
    return fleet

@fleet_router.post('/', status_code=status.HTTP_201_CREATED)
def create_fleet(request: FleetRequest, db: Session=Depends(get_db)):
    new_fleet = fleet_operation.create_fleet(request=request, db=db)
    return new_fleet

@fleet_router.delete('/{id}', status_code=status.HTTP_200_OK)
def delete_fleet(id: int, db: Session=Depends(get_db)):
    msg = fleet_operation.delete_fleet(id, db)
    return msg

@fleet_router.put('/{id}', status_code=status.HTTP_202_ACCEPTED)
def update_fleet(id: int, request: FleetRequest, db: Session=Depends(get_db)):
    fleet = fleet_operation.update_fleet(id, request, db)
    return fleet