from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from src.database import models
from src.api import schemas
from . import fleet_curd
from src.logger import logging
from src.exception import TMSException
import sys

def get_all_vehicles(fleet_id: Optional[int], db: Session):
    """Retrieve all vehicles"""
    try:
        if fleet_id:
            fleet =  fleet_curd.get_fleet(id=fleet_id, db=db)
            if not fleet:
                logging.debug(f"Fleet with id {fleet_id} not found")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet with id {fleet_id} not found")
            
            vehicles = db.query(models.Vehicles).filter(models.Vehicles.fleet_id == fleet_id).all()
        else:
            vehicles = db.query(models.Vehicles).all()
            
        return vehicles
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Failed to load all vehicles {e}")
        raise TMSException(error_message=f"Failed to load all vehicles {e}", error_detail=sys)

def get_vehicle(id:int, db: Session):
    "Retrieve a vehicle by its ID"
    try:
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == id).first()
        if not vehicle:
            return None
        return vehicle
    except Exception as e:
        logging.error(f"Unable to load vehicle {id}")
        raise TMSException(error_message=f"Unable to load vehicle {id}, error: {e}", error_detail=sys)
        
def create_vehicle(fleet_id: int, request: schemas.VehicleRequest, db: Session):
    """Add vehicle to the fleet"""
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == fleet_id).first()
        
        if not fleet:
            logging.debug(f"Fleet with id {fleet_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet with id {fleet_id} not found")
            
        new_vehicle = models.Vehicles(
            vehicle_name = request.vehicle_name,
            fleet_id = fleet_id,
            type = request.type,
            status = request.status,
            location = request.location
            )
        db.add(new_vehicle)
        db.flush()
        
        new_constraint = models.VehicleConstrain(
            vehicle_id=new_vehicle.id,
            vehicle_name=new_vehicle.vehicle_name,
            fleet=fleet.fleet_name,
            type=new_vehicle.type,
            days=1,
            payload=10000,
            volume=40.0,
            time_window="00:00-23:59",
            max_distance=1200.0,
            max_visits=15
        )
        
        db.add(new_constraint)
        
        fleet.total_vehicles += 1
        if request.status == "available":
            fleet.available_vehicles += 1
        
        db.commit()
        db.refresh(new_vehicle)
        
        logging.info(f"Vehicle added for fleet {fleet_id} with request: {request}")
        
        return new_vehicle
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Vehicle not created for fleet {fleet_id}: {e}")
        raise TMSException(error_message=f"Vehicle not created: {e}", error_detail=sys)
        
def update_vehicle(vehicle_id: int, request: schemas.VehicleRequest, db: Session):
    """Update a vehicle and adjust fleet vehicle counts if status changes."""
    try: 
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id==vehicle_id).first()
        if not vehicle:
            logging.debug(f"Vehicle with id {vehicle_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {vehicle_id} not found"
            )
            
        fleet = db.query(models.Fleets).filter(models.Fleets.id == vehicle.fleet_id).first()
        if not fleet:
            logging.debug(f"Fleet with id {vehicle.fleet_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {vehicle.fleet_id} not found"
            )
        
        old_status = vehicle.status
        new_status = request.status
        
        vehicle.vehicle_name = request.vehicle_name
        vehicle.type = request.type
        vehicle.status = new_status
        vehicle.location = request.location
        
        constraint = db.query(models.VehicleConstrain).filter(models.VehicleConstrain.vehicle_id == vehicle_id).first()
        if constraint:
            constraint.vehicle_name = request.vehicle_name
            constraint.type = request.type
            constraint.fleet = fleet.fleet_name
        
        if old_status != new_status:
            if old_status == "available":
                fleet.available_vehicles -= 1
            if new_status == "available":
                fleet.available_vehicles += 1
        
        db.commit()
        db.refresh(vehicle)
        
        logging.info(f"Vehicle with id {vehicle_id} updated with request: {request}")
        
        return vehicle
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Unable to update vehicle id {vehicle_id}, error: {e}")
        raise TMSException(error_message=f"Unable to update vehicle id {vehicle_id}, error: {e}", error_detail=sys)
        
def delete_vehicle(vehicle_id: int, db: Session):
    """Delete a vehicle AND its constraint, then update fleet counts."""
    try:
        # Get vehicle (with constraint pre-loaded to avoid extra query)
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == vehicle_id).first()
        if not vehicle:
            logging.debug(f"Vehicle with id {vehicle_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {vehicle_id} not found"
            )

        # Get fleet for count updates
        fleet = db.query(models.Fleets).filter(models.Fleets.id == vehicle.fleet_id).first()
        if not fleet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {vehicle.fleet_id} not found"
            )

        # Update fleet counts
        fleet.total_vehicles -= 1
        if vehicle.status == "available":
            fleet.available_vehicles -= 1

        db.delete(vehicle)
        db.commit()
        
        logging.info(f"Vehicle {vehicle_id} and its constraint deleted successfully")
        
        return {"detail": f"Vehicle {vehicle_id} and its constraint deleted successfully"}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Unable to delete vehicle {vehicle_id}: {e}")
        raise TMSException(error_message=f"Unable to delete vehicle {vehicle_id}: {e}", error_detail=sys)