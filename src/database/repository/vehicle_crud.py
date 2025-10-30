from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from src.database import models
from src.api import schemas


def get_vehicle(id:int, db: Session):
    "Retrieve a vehicle by its ID"
    try:
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {id} not found"
            )
        return vehicle
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load vehicle {id}, error: {e}"
        )
        
def create_vehicle(fleet_id: int, request: schemas.VehicleRequest, db: Session):
    """Add vehicle to the fleet"""
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == fleet_id).first()
        
        if not fleet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {fleet_id} not found"
            )
            
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
            payload=1000.0,
            volume=10.0,
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
        return new_vehicle
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Vehicle not created: {e}"
        )
        
def update_vehicle(vehicle_id: int, request: schemas.VehicleRequest, db: Session):
    """Update a vehicle and adjust fleet vehicle counts if status changes."""
    try: 
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id==vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {vehicle_id} not found"
            )
            
        fleet = db.query(models.Fleets).filter(models.Fleets.id == vehicle.fleet_id).first()
        if not fleet:
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
        return vehicle
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update vehicle id {vehicle_id}, error: {e}"
        )
        
def delete_vehicle(vehicle_id: int, db: Session):
    """Delete a vehicle AND its constraint, then update fleet counts."""
    try:
        # 1. Get vehicle (with constraint pre-loaded to avoid extra query)
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {vehicle_id} not found"
            )

        # 2. Get fleet for count updates
        fleet = db.query(models.Fleets).filter(models.Fleets.id == vehicle.fleet_id).first()
        if not fleet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {vehicle.fleet_id} not found"
            )

        # # 3. Delete related constraint FIRST
        # constraint = db.query(models.VehicleConstrain).filter(
        #     models.VehicleConstrain.vehicle_id == vehicle_id
        # ).first()
        # if constraint:
        #     db.delete(constraint)  # Remove constraint

        # 4. Update fleet counts
        fleet.total_vehicles -= 1
        if vehicle.status == "available":
            fleet.available_vehicles -= 1

        # 5. Delete vehicle
        db.delete(vehicle)

        # 6. Commit all changes
        db.commit()
        return {"message": f"Vehicle {vehicle_id} and its constraint deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete vehicle {vehicle_id}: {e}"
        )
        
def update_vehicle_constraint(vehicle_id: int, request: schemas.VehicleConstrainRequest, db: Session):
    """Update the constraints for a specific vehicle."""
    try:
        constraint = db.query(models.VehicleConstrain).filter(models.VehicleConstrain.vehicle_id == vehicle_id).first()
        if not constraint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Constraint for vehicle id {vehicle_id} not found"
            )
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with id {vehicle_id} not found"
            )
        fleet = db.query(models.Fleets).filter(models.Fleets.id == vehicle.fleet_id).first()
        if not fleet:
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
        return constraint
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update constraint for vehicle id {vehicle_id}, error: {e}"
        )