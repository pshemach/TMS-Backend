from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.database.services import fleet_curd
from src.api import schemas
from src.database import database, models

get_db = database.get_db

router = APIRouter(prefix='/fleet', tags=['fleet'])

# === Helper: Enrich Fleet ===
def _enrich_fleet(fleet: models.Fleets) -> schemas.FleetResponse:
    vehicles = [_enrich_vehicle(vehicle) for vehicle in fleet.vehicles]
    return schemas.FleetResponse(
        id=fleet.id,
        fleet_name=fleet.fleet_name,
        type=fleet.type,
        region=fleet.region,
        manager=fleet.manager,
        status=fleet.status,
        total_vehicles=fleet.total_vehicles,
        available_vehicles=fleet.available_vehicles,
        vehicles=vehicles
    )
    
# === Helper: Enrich Vehicle ===
def _enrich_vehicle(vehicle: models.Vehicles) -> schemas.VehicleResponse:
    return schemas.VehicleResponse(
        id=vehicle.id,
        vehicle_name=vehicle.vehicle_name,
        type=vehicle.type,
        status=vehicle.status,
        location=vehicle.location,
        fleet_id=vehicle.fleet_id,
        constraint=schemas.VehicleConstrainResponse(
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
            max_visits=vehicle.constraint.max_visits 
        )
    )
    
@router.get('/', status_code=status.HTTP_200_OK, response_model=List[schemas.FleetResponse])
def get_all_fleet(db: Session = Depends(get_db)):
    """Retrieve all fleets with their vehicles."""
    try:
        fleets = fleet_curd.all_fleets(db)
        if not fleets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No fleets available in database")
        return [_enrich_fleet(fleet) for fleet in fleets]
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load fleets, error: {e}"
        )

@router.get('/{id}', status_code=status.HTTP_200_OK, response_model=schemas.FleetResponse)
def get_fleet(id: int, db: Session=Depends(get_db)):
    """Retrieve a fleet by ID with its vehicles."""
    try: 
        fleet = fleet_curd.get_fleet(id=id, db=db)
        if not fleet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet with id {id} not found")
        return _enrich_fleet(fleet)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load fleet {id}, error: {e}"
            )

@router.post('/', status_code=status.HTTP_201_CREATED, response_model=schemas.FleetResponse)
def create_fleet(request: schemas.FleetRequest, db: Session=Depends(get_db)):
    """Create new fleet"""
    try:
        new_fleet = fleet_curd.create_fleet(request=request, db=db)
        return _enrich_fleet(new_fleet)
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Unable to create fleet, error: {e}"
        )

@router.delete('/{id}', status_code=status.HTTP_200_OK)
def delete_fleet(id: int, db: Session = Depends(get_db)):
    """Delete a fleet and its associated vehicles."""
    try:
        msg = fleet_curd.delete_fleet(id, db)
        return msg
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete fleet {id}, error: {e}"
        )

@router.put('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.FleetResponse)
def update_fleet(id: int, request: schemas.FleetRequest, db: Session = Depends(get_db)):
    """Update a fleet's metadata."""
    try:
        fleet = fleet_curd.update_fleet(id, request, db)
        return _enrich_fleet(fleet)
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update fleet {id}, error: {e}"
        )