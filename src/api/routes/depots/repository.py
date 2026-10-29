import sys

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.routes.depots import schemas
from src.infrastructure.database import models
from src.infrastructure.exceptions import TMSException
from src.infrastructure.logging import logging


def _active_depots(db: Session):
    return db.query(models.Location).filter(
        models.Location.is_deleted.is_(False),
        models.Location.location_type == models.LocationType.DEPOT,
    )


def get_all(db: Session):
    try:
        return _active_depots(db).all()
    except Exception as e:
        logging.error(f"Failed to fetch depots: {e}")
        raise TMSException(f"Unable to load depots: {e}", sys)


def get_depot(id: int, db: Session):
    try:
        return _active_depots(db).filter(models.Location.id == id).first()
    except Exception as e:
        logging.error(f"Failed to fetch depot {id}: {e}")
        raise TMSException(f"Unable to load depot {id}: {e}", sys)


def create(request: schemas.DepotRequest, db: Session):
    try:
        row = models.Location(
            location_code=request.location_code,
            location_name=request.location_name,
            address=request.address,
            brand=None,
            district=request.district,
            latitude=request.latitude,
            longitude=request.longitude,
            location_type=models.LocationType.DEPOT,
            matrix_status=models.MatrixStatus.TO_CREATE,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logging.info(f"Created depot with id {row.id}")
        return row
    except IntegrityError as e:
        db.rollback()
        logging.error(f"Integrity error creating depot: {e}")
        raise TMSException(
            f"Depot creation failed - duplicate or constraint violation: {e}", sys
        )
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create depot: {e}")
        raise TMSException(f"Depot creation failed: {e}", sys)


def delete(id: int, db: Session):
    try:
        depot = _active_depots(db).filter(models.Location.id == id).first()
        if not depot:
            return None

        depot.location_code = f"{depot.location_code}__deleted_{depot.id}"
        depot.soft_delete()
        db.commit()
        logging.info(f"Soft-deleted depot with id {id}")
        return {"message": f"Depot with id {id} deleted"}
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete depot {id}: {e}")
        raise TMSException(f"Unable to delete depot {id}: {e}", sys)


def update(id: int, request: schemas.DepotRequest, db: Session):
    try:
        depot = _active_depots(db).filter(models.Location.id == id).first()
        if not depot:
            return None

        gps_changed = (
            depot.latitude != request.latitude
            or depot.longitude != request.longitude
        )
        depot.location_code = request.location_code
        depot.location_name = request.location_name
        depot.address = request.address
        depot.district = request.district
        depot.latitude = request.latitude
        depot.longitude = request.longitude
        depot.location_type = models.LocationType.DEPOT
        if gps_changed:
            depot.matrix_status = models.MatrixStatus.TO_UPDATE

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


def depot_coords(depot: models.Location) -> dict:
    return {
        "location_code": depot.location_code,
        "latitude": depot.latitude,
        "longitude": depot.longitude,
    }
