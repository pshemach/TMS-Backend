from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.database import models
from src.api import schemas
from src.logger import logging
from src.exception import TMSException
import sys


def get_all(db: Session):
    try:
        depots = db.query(models.GPSMaster).filter(models.GPSMaster.brand == models.Depot.BRAND).all()
        return depots
    except Exception as e:
        logging.error(f"Failed to fetch depots: {e}")
        raise TMSException(f"Unable to load depots: {e}", sys)
    
def get_depot(id: int, db: Session):
    try:
        depot = db.query(models.GPSMaster).filter(
            models.GPSMaster.id == id,
            models.GPSMaster.brand ==  models.Depot.BRAND
        ).first()
        return depot
    except Exception as e:
        logging.error(f"Failed to fetch depot {id}: {e}")
        raise TMSException(f"Unable to load depot {id}: {e}", sys)

def create(request: schemas.DepotRequest, db: Session):
    try:
        new_depot = models.GPSMaster(
            shop_code=request.depot_code, 
            location=request.location,
            address=request.address, 
            brand= models.Depot.BRAND,  # Hardcoded as depot
            district=request.district, 
            latitude=request.latitude,
            longitude=request.longitude,
            matrix_status='to_create'
        )
        db.add(new_depot)
        db.commit()
        db.refresh(new_depot)
        logging.info(f"Created depot with id {new_depot.id}")
        return new_depot
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error creating depot: {e}")
        raise TMSException(f"Depot creation failed - duplicate or constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create depot: {e}")
        raise TMSException(f"Depot creation failed: {e}", sys)

def delete(id: int, db: Session):
    try:
        depot = db.query(models.GPSMaster).filter(
            models.GPSMaster.id == id,
            models.GPSMaster.brand ==  models.Depot.BRAND
        ).first()
        
        if not depot:
            return None  # Let route handle 404
        
        db.delete(depot)
        db.commit()
        logging.info(f"Deleted depot with id {id}")
        return {"message": f"Depot with id {id} deleted"}
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete depot {id}: {e}")
        raise TMSException(f"Unable to delete depot {id}: {e}", sys)
    
def update(id: int, request: schemas.DepotRequest, db: Session):
    try:
        depot = db.query(models.GPSMaster).filter(
            models.GPSMaster.id == id,
            models.GPSMaster.brand ==  models.Depot.BRAND
        ).first()
        
        if not depot:
            return None  # Let route handle 404

        gps_changed = (
            depot.latitude != request.latitude or 
            depot.longitude != request.longitude
        )
        
        # Update fields
        depot.shop_code = request.depot_code
        depot.location = request.location
        depot.address = request.address
        depot.brand =  models.Depot.BRAND # Ensure it remains a depot
        depot.district = request.district
        depot.latitude = request.latitude
        depot.longitude = request.longitude
        depot.matrix_status = 'to_update' if gps_changed else depot.matrix_status
        
        db.commit()
        db.refresh(depot)
        logging.info(f"Updated depot with id {id}")
        return depot
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error updating depot {id}: {e}")
        raise TMSException(f"Depot update failed - constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update depot {id}: {e}")
        raise TMSException(f"Unable to update depot {id}: {e}", sys)
    
def depot_coords(depot: models.GPSMaster) -> dict:
    """Return only the fields the API needs."""
    return {
        "depot_code": depot.shop_code,
        "latitude": depot.latitude,
        "longitude": depot.longitude,
    }