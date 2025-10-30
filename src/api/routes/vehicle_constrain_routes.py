from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.repository import vehicle_crud
from src.api import schemas
from src.database import database

get_db = database.get_db

vehicle_constraint_router = APIRouter(
    prefix='/vehicle-constraint',
    tags=['vehicle-constraint']
)

@vehicle_constraint_router.put('/{vehicle_id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.VehicleConstrainResponse)
def update_vehicle_constraint(vehicle_id: int, request: schemas.VehicleConstrainRequest, db: Session = Depends(get_db)):
    """
    Update the constraints for a specific vehicle.
    """
    try:
        constraint = vehicle_crud.update_vehicle_constraint(vehicle_id=vehicle_id, request=request, db=db)
        return constraint
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update constraint for vehicle {vehicle_id}, error: {e}"
        )