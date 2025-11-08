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
        shops = db.query(models.GPSMaster).filter(models.GPSMaster.brand != models.Depot.BRAND).all()
        return shops
    except Exception as e:
        logging.error(f"Failed to fetch shops: {e}")
        raise TMSException(f"Unable to load shops: {e}", sys)

def get_shop(id: int, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(
            models.GPSMaster.id == id,
            models.GPSMaster.brand != models.Depot.BRAND
            ).first()
        return shop
    except Exception as e:
        logging.error(f"Failed to fetch shop {id}: {e}")
        raise TMSException(f"Unable to load shop {id}: {e}", sys)

def get_shop_code(shop_code: str, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(
            models.GPSMaster.shop_code == shop_code,
            models.GPSMaster.brand != models.Depot.BRAND
            ).first()
        return shop
    except Exception as e:
        logging.error(f"Failed to fetch shop with code {shop_code}: {e}")
        raise TMSException(f"Unable to load shop with code {shop_code}: {e}", sys)
    
def create(request: schemas.ShopRequest, db: Session):
    try:
        new_shop = models.GPSMaster(
            shop_code=request.shop_code, 
            location=request.location,
            address=request.address, 
            brand=request.brand,
            district=request.district, 
            latitude=request.latitude,
            longitude=request.longitude,
            matrix_status='to_create'
            )
        db.add(new_shop)
        db.commit()
        db.refresh(new_shop)
        logging.info(f"Created shop with id {new_shop.id}")
        return new_shop
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error creating shop: {e}")
        raise TMSException(f"Shop creation failed - duplicate or constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create shop: {e}")
        raise TMSException(f"Shop creation failed: {e}", sys)

def delete(id: int, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == id).first()
        
        if not shop:
            return None  # Let route handle 404
        
        db.delete(shop)
        db.commit()
        logging.info(f"Deleted shop with id {id}")
        return {"message": f"Shop with id {id} deleted"}
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete shop {id}: {e}")
        raise TMSException(f"Unable to delete shop {id}: {e}", sys)
    
def update(id: int, request: schemas.ShopRequest, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == id)
        if not shop.first():
            return None  # Let route handle 404

        gps_changed = (
        shop.first().latitude != request.latitude or 
        shop.first().longitude != request.longitude
        )
        current_status = shop.first().matrix_status
        
        if gps_changed:
            shop.update({
                models.GPSMaster.shop_code : request.shop_code,
                models.GPSMaster.location : request.location,
                models.GPSMaster.address : request.address,
                models.GPSMaster.brand : request.brand,
                models.GPSMaster.district : request.district,
                models.GPSMaster.latitude : request.latitude,
                models.GPSMaster.longitude : request.longitude,
                models.GPSMaster.matrix_status : 'to_update'
            })
        else:
            shop.update({
                models.GPSMaster.shop_code : request.shop_code,
                models.GPSMaster.location : request.location,
                models.GPSMaster.address : request.address,
                models.GPSMaster.brand : request.brand,
                models.GPSMaster.district : request.district,
                models.GPSMaster.latitude : request.latitude,
                models.GPSMaster.longitude : request.longitude,
                models.GPSMaster.matrix_status : current_status
            })
        db.commit()
        logging.info(f"Updated shop with id {id}")
        return shop.first()
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error updating shop {id}: {e}")
        raise TMSException(f"Shop update failed - constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update shop {id}: {e}")
        raise TMSException(f"Unable to update shop {id}: {e}", sys)
    
def shop_coords(shop: models.GPSMaster) -> dict:
    """Return only the fields the API needs."""
    return {
        "shop_code": shop.shop_code,
        "latitude":  shop.latitude,
        "longitude": shop.longitude,
    }