from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.repository import fleet_curd, vehicle_curd
from src.api import schemas
from src.database import database
from typing import List, Optional
from src.database import models

get_db = database.get_db

vehicle_router = APIRouter(
    prefix='/vehicle',
    tags=['vehicle']
)

@vehicle_router.get('/', status_code=status.HTTP_200_OK, response_model=List[schemas.VehicleResponse])
def get_all_vehicles(fleet_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Retrieve all vehicles, optionally filtered by fleet_id.
    """
    try:
        if fleet_id:
            # Verify fleet exists
            fleet = fleet_curd.get_fleet(id=fleet_id, db=db)
            vehicles = db.query(models.Vehicles).filter(models.Vehicles.fleet_id == fleet_id).all()
        else:
            vehicles = db.query(models.Vehicles).all()
        return vehicles
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load vehicles, error: {e}"
        )

@vehicle_router.get('/{id}', status_code=status.HTTP_200_OK, response_model=schemas.VehicleResponse)
def get_vehicle(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a vehicle by ID.
    """
    try:
        vehicle = vehicle_curd.get_vehicle(id=id, db=db)
        return vehicle
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load vehicle {id}, error: {e}"
        )

@vehicle_router.post('/{fleet_id}', status_code=status.HTTP_201_CREATED, response_model=schemas.VehicleResponse)
def create_vehicle(fleet_id: int, request: schemas.VehicleRequest, db: Session = Depends(get_db)):
    """
    Create a new vehicle in the specified fleet with default constraints.
    """
    try:
        new_vehicle = vehicle_curd.create_vehicle(fleet_id=fleet_id, request=request, db=db)
        return new_vehicle
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Unable to create vehicle, error: {e}"
        )

@vehicle_router.put('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.VehicleResponse)
def update_vehicle(id: int, request: schemas.VehicleRequest, db: Session = Depends(get_db)):
    """
    Update a vehicle's details and adjust fleet vehicle counts if status changes.
    """
    try:
        vehicle = vehicle_curd.update_vehicle(vehicle_id=id, request=request, db=db)
        return vehicle
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update vehicle {id}, error: {e}"
        )

@vehicle_router.delete('/{id}', status_code=status.HTTP_200_OK)
def delete_vehicle(id: int, db: Session = Depends(get_db)):
    """
    Delete a vehicle and update fleet vehicle counts.
    """
    try:
        msg = vehicle_curd.delete_vehicle(vehicle_id=id, db=db)
        return msg
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete vehicle {id}, error: {e}"
        )