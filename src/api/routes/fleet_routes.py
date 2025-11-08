from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.database.services import fleet_curd
from src.api import schemas
from src.database import database

get_db = database.get_db

fleet_router = APIRouter(
        prefix='/fleet',
    tags=['fleet']
)

@fleet_router.get('/', status_code=status.HTTP_200_OK, response_model=List[schemas.FleetResponse])
def get_all_fleet(db: Session = Depends(get_db)):
    """Retrieve all fleets with their vehicles."""
    try:
        fleets = fleet_curd.all_fleets(db)
        return fleets
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load fleets, error: {e}"
        )

@fleet_router.get('/{id}', status_code=status.HTTP_200_OK, response_model=schemas.FleetResponse)
def get_fleet(id: int, db: Session=Depends(get_db)):
    """Retrieve a fleet by ID with its vehicles."""
    try: 
        fleet = fleet_curd.get_fleet(id=id, db=db)
        return fleet
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load fleet {id}, error: {e}"
            )

@fleet_router.post('/', status_code=status.HTTP_201_CREATED, response_model=schemas.FleetResponse)
def create_fleet(request: schemas.FleetRequest, db: Session=Depends(get_db)):
    """Create new fleet"""
    try:
        new_fleet = fleet_curd.create_fleet(request=request, db=db)
        return new_fleet
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Unable to create fleet, error: {e}"
        )

@fleet_router.delete('/{id}', status_code=status.HTTP_200_OK)
def delete_fleet(id: int, db: Session = Depends(get_db)):
    """Delete a fleet and its associated vehicles."""
    try:
        msg = fleet_curd.delete_fleet(id, db)
        return msg
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete fleet {id}, error: {e}"
        )

@fleet_router.put('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.FleetResponse)
def update_fleet(id: int, request: schemas.FleetRequest, db: Session = Depends(get_db)):
    """Update a fleet's metadata."""
    try:
        fleet = fleet_curd.update_fleet(id, request, db)
        return fleet
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update fleet {id}, error: {e}"
        )