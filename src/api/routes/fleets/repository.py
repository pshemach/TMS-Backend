from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.infrastructure.database import models
from src.api.routes.fleets import schemas
from src.infrastructure.logging import logging
from src.infrastructure.exceptions import TMSException
import sys


def all_fleets(db: Session):
    """Retrieve all fleets from the database."""
    try:
        fleets = db.query(models.Fleet).filter(models.Fleet.is_deleted.is_(False)).all()
        if not fleets:
            return  None
        return fleets
    except Exception as e:
        logging.error(f"Unable to load fleets, error: {e}")
        raise TMSException(error_message=f"Unable to load fleets, error: {e}", error_detail=sys)
        
def get_fleet(id: int, db: Session):
    """Retrieve a fleet by ID."""
    try:
        fleet = fleet = db.query(models.Fleet).filter(models.Fleet.id == id).first()
        if not fleet:
            return None
        return fleet
    except Exception as e:
        logging.error(f"Unable to load fleet {id}, error: {e}")
        raise TMSException(error_message=f"Unable to load fleet {id}, error: {e}", error_detail=sys)

def create_fleet(request: schemas.FleetRequest, db: Session):
    """Create a new fleet."""
    try:
        new_fleet = models.Fleet(
            fleet_name=request.fleet_name,
            type=request.type,
            region=request.region,
            manager=request.manager,
            status=request.status,
            total_vehicles=0,
            available_vehicles=0
        )
        
        db.add(new_fleet)
        db.commit()
        db.refresh(new_fleet)
        
        logging.info(f"New fleet created with request: {request}")
        return new_fleet
    except Exception as e:
        db.rollback()
        logging.error(f"Fleet with {request.dict()} not created: {e}")
        raise TMSException(error_message=f"Fleet with {request.dict()} not created: {e}", error_detail=sys)
        
def delete_fleet(id: int, db: Session):
    """Delete a fleet by ID."""
    try:
        fleet = db.query(models.Fleet).filter(models.Fleet.id == id).first()
        if not fleet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {id} not found"
            )
        fleet.soft_delete()
        db.commit()
        
        logging.info(f"Fleet with id {id} deleted")
        return {"message": f"Fleet with id {id} deleted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Unable to delete fleet {id}, error: {e}")
        raise TMSException(f"Unable to delete fleet {id}, error: {e}", sys)

def update_fleet(id: int, request: schemas.FleetRequest, db: Session):
    """Update fleet metadata (excludes vehicle counts)."""
    try:
        fleet = db.query(models.Fleet).filter(models.Fleet.id == id)
        if not fleet.first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {id} not found"
            )
        
        update_data = {}
        if request.fleet_name is not None:
            update_data[models.Fleet.fleet_name] = request.fleet_name
        if request.type is not None:
            update_data[models.Fleet.type] = request.type
        if request.region is not None:
            update_data[models.Fleet.region] = request.region
        if request.manager is not None:
            update_data[models.Fleet.manager] = request.manager
        if request.status is not None:
            update_data[models.Fleet.status] = request.status
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )
        
        fleet.update(update_data)
        db.commit()
        updated_fleet = fleet.first()
        db.refresh(updated_fleet)
        
        logging.info(f"Fleet with id {id} updated with request: {request}")
        return updated_fleet
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Unable to update fleet id {id}, error: {e}")
        raise HTTPException(f"Unable to update fleet id {id}, error: {e}", sys)