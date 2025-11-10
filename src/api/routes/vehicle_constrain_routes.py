from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.services import vehicle_constraint_curd
from src.api import schemas
from src.database import database, models

get_db = database.get_db

router = APIRouter(prefix='/vehicle-constraint', tags=['vehicle-constraint'])

# === Helper: Enrich Vehicle Constraint ===
def _enrich(constraint: models.VehicleConstrain) -> schemas.VehicleConstrainResponse:
    return schemas.VehicleConstrainResponse(
        id=constraint.id,
        fleet=constraint.fleet,
        vehicle_id=constraint.vehicle_id,
        vehicle_name=constraint.vehicle_name,
        type=constraint.type,
        days=constraint.days,
        payload=constraint.payload,
        volume=constraint.volume,
        time_window=constraint.time_window,
        max_distance=constraint.max_distance,
        max_visits=constraint.max_visits     
    )

# === Update vehicle constraint ===
@router.put('/{vehicle_id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.VehicleConstrainResponse)
def update_vehicle_constraint(vehicle_id: int, request: schemas.VehicleConstrainRequest, db: Session = Depends(get_db)):
    """
    Update constraints for a specific vehicle.
    """
    try:
        constraint = vehicle_constraint_curd.update_vehicle_constraint(vehicle_id=vehicle_id, request=request, db=db)
        if not constraint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Constraint for vehicle id {vehicle_id} not found"
            )
        return _enrich(constraint)
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update constraint for vehicle {vehicle_id}, error: {e}"
        )