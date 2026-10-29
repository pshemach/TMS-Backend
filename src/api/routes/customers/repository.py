import sys

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.routes.customers import schemas
from src.infrastructure.database import models
from src.infrastructure.exceptions import TMSException
from src.infrastructure.logging import logging


def _active_customers(db: Session):
    return db.query(models.Location).filter(
        models.Location.is_deleted.is_(False),
        models.Location.location_type == models.LocationType.CUSTOMER,
    )


def get_all(db: Session):
    try:
        return _active_customers(db).all()
    except Exception as e:
        logging.error(f"Failed to fetch customers: {e}")
        raise TMSException(f"Unable to load customers: {e}", sys)


def get_by_id(id: int, db: Session):
    try:
        return _active_customers(db).filter(models.Location.id == id).first()
    except Exception as e:
        logging.error(f"Failed to fetch customer {id}: {e}")
        raise TMSException(f"Unable to load customer {id}: {e}", sys)


def get_by_code(location_code: str, db: Session):
    try:
        return (
            _active_customers(db)
            .filter(models.Location.location_code == location_code)
            .first()
        )
    except Exception as e:
        logging.error(f"Failed to fetch customer with code {location_code}: {e}")
        raise TMSException(f"Unable to load customer with code {location_code}: {e}", sys)


# Back-compat aliases used by older callers
get_shop = get_by_id
get_shop_code = get_by_code


def create(request: schemas.CustomerRequest, db: Session):
    try:
        row = models.Location(
            location_code=request.location_code,
            location_name=request.location_name,
            address=request.address,
            brand=request.brand,
            district=request.district,
            latitude=request.latitude,
            longitude=request.longitude,
            location_type=models.LocationType.CUSTOMER,
            matrix_status=models.MatrixStatus.TO_CREATE,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logging.info(f"Created customer with id {row.id}")
        return row
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error creating customer: {e}")
        raise TMSException(
            f"Customer creation failed - duplicate or constraint violation: {e}", sys
        )
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create customer: {e}")
        raise TMSException(f"Customer creation failed: {e}", sys)


def delete(id: int, db: Session):
    try:
        customer = _active_customers(db).filter(models.Location.id == id).first()
        if not customer:
            return None

        linked_orders = (
            db.query(models.Order)
            .filter(
                models.Order.location_id == id,
                models.Order.is_deleted.is_(False),
            )
            .count()
        )
        if linked_orders:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer {id} is referenced by {linked_orders} order(s)",
            )

        customer.location_code = f"{customer.location_code}__deleted_{customer.id}"
        customer.soft_delete()
        db.commit()
        logging.info(f"Soft-deleted customer with id {id}")
        return {"message": f"Customer with id {id} deleted"}
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        db.rollback()
        logging.error(f"Failed to delete customer {id}: {e}")
        raise TMSException(f"Unable to delete customer {id}: {e}", sys)


def update(id: int, request: schemas.CustomerRequest, db: Session):
    try:
        customer = _active_customers(db).filter(models.Location.id == id).first()
        if not customer:
            return None

        gps_changed = (
            customer.latitude != request.latitude
            or customer.longitude != request.longitude
        )
        customer.location_code = request.location_code
        customer.location_name = request.location_name
        customer.address = request.address
        customer.brand = request.brand
        customer.district = request.district
        customer.latitude = request.latitude
        customer.longitude = request.longitude
        if gps_changed:
            customer.matrix_status = models.MatrixStatus.TO_UPDATE

        db.commit()
        db.refresh(customer)
        logging.info(f"Updated customer with id {id}")
        return customer
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error updating customer {id}: {e}")
        raise TMSException(f"Customer update failed - constraint violation: {e}", sys)
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update customer {id}: {e}")
        raise TMSException(f"Unable to update customer {id}: {e}", sys)


def location_coords(loc: models.Location) -> dict:
    return {
        "location_code": loc.location_code,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
    }


# Back-compat
shop_coords = location_coords
