from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.database import models
from src.api import schemas
from src.logger import logging
from src.exception import TMSException
import sys

def update_vehicle_constraint(vehicle_id: int, request: schemas.VehicleConstrainRequest, db: Session):
    """Update the constraints for a specific vehicle."""
    try:
        constraint = db.query(models.VehicleConstrain).filter(models.VehicleConstrain.vehicle_id == vehicle_id).first()
        
        if not constraint:
            logging.debug(f"No constrain found for vehicle id {vehicle_id}")
            return None
        
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == vehicle_id).first()
        if not vehicle:
            logging.debug(f"No vehicle found for vehicle id {vehicle_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {vehicle_id} not found"
            )
            
        fleet = db.query(models.Fleets).filter(models.Fleets.id == vehicle.fleet_id).first()
        if not fleet:
            logging.debug(f"No fleet found for vehicle id {vehicle_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {vehicle.fleet_id} not found"
            )
        
        constraint.type = vehicle.type
        constraint.payload = request.payload
        constraint.volume = request.volume
        constraint.time_window = request.time_window
        constraint.max_distance = request.max_distance
        constraint.max_visits = request.max_visits
        constraint.vehicle_name = vehicle.vehicle_name
        constraint.fleet = fleet.fleet_name
        
        db.commit()
        db.refresh(constraint)
        
        logging.info(f"Constrain for vehicle id {vehicle_id} updated with request: {request}")
        
        return constraint
    except Exception as e:
        db.rollback()
        raise TMSException(f"Unable to update constraint for vehicle id {vehicle_id}, error: {e}", sys)