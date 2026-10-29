from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.routes.vehicles import repository as vehicle_crud
from src.api.routes.vehicles import schemas
from src.infrastructure.database import models
from src.api.deps import get_db
from typing import List, Optional

router = APIRouter(tags=['vehicle'])

def _enrich_vehicle(vehicle: models.Vehicles) -> schemas.VehicleResponse:
    constraint = None
    if vehicle.constraint is not None:
        constraint = schemas.VehicleConstrainResponse(
            id=vehicle.constraint.id,
            fleet=vehicle.constraint.fleet,
            vehicle_id=vehicle.constraint.vehicle_id,
            vehicle_name=vehicle.constraint.vehicle_name,
            type=vehicle.constraint.type,
            days=vehicle.constraint.days,
            payload=vehicle.constraint.payload,
            volume=vehicle.constraint.volume,
            time_window=vehicle.constraint.time_window,
            max_distance=vehicle.constraint.max_distance,
            max_visits=vehicle.constraint.max_visits,
        )
    return schemas.VehicleResponse(
        id=vehicle.id,
        vehicle_name=vehicle.vehicle_name,
        type=vehicle.type,
        status=vehicle.status,
        location=vehicle.location,
        fleet_id=vehicle.fleet_id,
        constraint=constraint,
    )

@router.get("/vehicle", status_code=status.HTTP_200_OK, response_model=List[schemas.VehicleResponse])
def get_all_vehicles(fleet_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Retrieve all vehicles, optionally filtered by fleet_id.
    """
    try:
        vehicles = vehicle_crud.get_all_vehicles(fleet_id=fleet_id, db=db) or []
        return [_enrich_vehicle(vehicle) for vehicle in vehicles]
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load vehicles, error: {e}"
        )

@router.get('/vehicle/{id}', status_code=status.HTTP_200_OK, response_model=schemas.VehicleResponse)
def get_vehicle(id: int, db: Session = Depends(get_db)):
    """
    Retrieve a vehicle by ID.
    """
    try:
        vehicle = vehicle_crud.get_vehicle(id=id, db=db)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {id} not found"
            )
        return _enrich_vehicle(vehicle)
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load vehicle {id}, error: {e}"
        )

@router.post('/vehicle/{fleet_id}', status_code=status.HTTP_201_CREATED, response_model=schemas.VehicleResponse)
def create_vehicle(fleet_id: int, request: schemas.VehicleRequest, db: Session = Depends(get_db)):
    """
    Create a new vehicle in the specified fleet with default constraints.
    """
    try:
        new_vehicle = vehicle_crud.create_vehicle(fleet_id=fleet_id, request=request, db=db)
        return _enrich_vehicle(new_vehicle)
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Unable to create vehicle, error: {e}"
        )

@router.put('/vehicle/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.VehicleResponse)
def update_vehicle(id: int, request: schemas.VehicleRequest, db: Session = Depends(get_db)):
    """
    Update a vehicle's details and adjust fleet vehicle counts if status changes.
    """
    try:
        vehicle = vehicle_crud.update_vehicle(vehicle_id=id, request=request, db=db)
        return _enrich_vehicle(vehicle)
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update vehicle {id}, error: {e}"
        )

@router.delete('/vehicle/{id}', status_code=status.HTTP_200_OK)
def delete_vehicle(id: int, db: Session = Depends(get_db)):
    """
    Delete a vehicle and update fleet vehicle counts.
    """
    try:
        msg = vehicle_crud.delete_vehicle(vehicle_id=id, db=db)
        return msg
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete vehicle {id}, error: {e}"
        )