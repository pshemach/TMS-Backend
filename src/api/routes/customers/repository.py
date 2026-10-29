from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.infrastructure.database import models
from src.api.routes.customers import schemas
from src.infrastructure.logging import logging
from src.infrastructure.exceptions import TMSException
import sys


def get_all(db: Session):
    try:
        customers = db.query(models.GPSMaster).filter(models.GPSMaster.brand != models.Depot.BRAND).all()
        return customers
    except Exception as e:
        logging.error(f"Failed to fetch customers: {e}")
        raise TMSException(f"Unable to load customers: {e}", sys)


def get_shop(id: int, db: Session):
    try:
        customer = db.query(models.GPSMaster).filter(
            models.GPSMaster.id == id,
            models.GPSMaster.brand != models.Depot.BRAND
        ).first()
        return customer
    except Exception as e:
        logging.error(f"Failed to fetch customer {id}: {e}")
        raise TMSException(f"Unable to load customer {id}: {e}", sys)


def get_shop_code(shop_code: str, db: Session):
    try:
        customer = db.query(models.GPSMaster).filter(
            models.GPSMaster.shop_code == shop_code,
            models.GPSMaster.brand != models.Depot.BRAND
        ).first()
        return customer
    except Exception as e:
        logging.error(f"Failed to fetch customer with code {shop_code}: {e}")
        raise TMSException(f"Unable to load customer with code {shop_code}: {e}", sys)


def create(request: schemas.CustomerRequest, db: Session):
    try:
        new_customer = models.GPSMaster(
            shop_code=request.shop_code,
            location=request.location,
            address=request.address,
            brand=request.brand,
            district=request.district,
            latitude=request.latitude,
            longitude=request.longitude,
            matrix_status='to_create'
        )
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        logging.info(f"Created customer with id {new_customer.id}")
        return new_customer
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error creating customer: {e}")
        raise TMSException(f"Customer creation failed - duplicate or constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create customer: {e}")
        raise TMSException(f"Customer creation failed: {e}", sys)


def delete(id: int, db: Session):
    try:
        customer = db.query(models.GPSMaster).filter(models.GPSMaster.id == id).first()

        if not customer:
            return None

        db.delete(customer)
        db.commit()
        logging.info(f"Deleted customer with id {id}")
        return {"message": f"Customer with id {id} deleted"}
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete customer {id}: {e}")
        raise TMSException(f"Unable to delete customer {id}: {e}", sys)


def update(id: int, request: schemas.CustomerRequest, db: Session):
    try:
        customer = db.query(models.GPSMaster).filter(models.GPSMaster.id == id)
        if not customer.first():
            return None

        gps_changed = (
            customer.first().latitude != request.latitude or
            customer.first().longitude != request.longitude
        )
        current_status = customer.first().matrix_status

        if gps_changed:
            customer.update({
                models.GPSMaster.shop_code: request.shop_code,
                models.GPSMaster.location: request.location,
                models.GPSMaster.address: request.address,
                models.GPSMaster.brand: request.brand,
                models.GPSMaster.district: request.district,
                models.GPSMaster.latitude: request.latitude,
                models.GPSMaster.longitude: request.longitude,
                models.GPSMaster.matrix_status: 'to_update'
            })
        else:
            customer.update({
                models.GPSMaster.shop_code: request.shop_code,
                models.GPSMaster.location: request.location,
                models.GPSMaster.address: request.address,
                models.GPSMaster.brand: request.brand,
                models.GPSMaster.district: request.district,
                models.GPSMaster.latitude: request.latitude,
                models.GPSMaster.longitude: request.longitude,
                models.GPSMaster.matrix_status: current_status
            })
        db.commit()
        logging.info(f"Updated customer with id {id}")
        return customer.first()
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error updating customer {id}: {e}")
        raise TMSException(f"Customer update failed - constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update customer {id}: {e}")
        raise TMSException(f"Unable to update customer {id}: {e}", sys)


def shop_coords(shop: models.GPSMaster) -> dict:
    """Return only the fields the API needs."""
    return {
        "shop_code": shop.shop_code,
        "latitude": shop.latitude,
        "longitude": shop.longitude,
    }
