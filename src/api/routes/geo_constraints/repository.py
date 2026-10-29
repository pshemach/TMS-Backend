from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.api.routes.geo_constraints import schemas
from src.infrastructure.database import models


def _get_location(location_id: int, db: Session) -> models.Location:
    loc = (
        db.query(models.Location)
        .filter(
            models.Location.id == location_id,
            models.Location.is_deleted.is_(False),
        )
        .first()
    )
    if not loc:
        raise HTTPException(status_code=404, detail=f"Customer {location_id} not found")
    return loc


def create_geo_constraint(
    request: schemas.GeoConstraintCreate, db: Session
) -> models.GeoConstraint:
    start = _get_location(request.start_location_id, db)
    end = _get_location(request.end_location_id, db)

    if start.id == end.id:
        raise HTTPException(status_code=400, detail="Start and end location must be different")

    if request.vehicle_id is None:
        existing_unassigned = (
            db.query(models.GeoConstraint)
            .filter(
                models.GeoConstraint.is_deleted.is_(False),
                models.GeoConstraint.start_location_id == start.id,
                models.GeoConstraint.end_location_id == end.id,
                models.GeoConstraint.vehicle_id.is_(None),
            )
            .first()
        )
        if existing_unassigned:
            raise HTTPException(
                status_code=400,
                detail="This route (start → end) already exists without a vehicle.",
            )

    if request.vehicle_id:
        vehicle = (
            db.query(models.Vehicle)
            .filter(
                models.Vehicle.id == request.vehicle_id,
                models.Vehicle.is_deleted.is_(False),
            )
            .first()
        )
        if not vehicle:
            raise HTTPException(
                status_code=404, detail=f"Vehicle {request.vehicle_id} not found"
            )

    geo = models.GeoConstraint(
        start_location_id=start.id,
        end_location_id=end.id,
        vehicle_id=request.vehicle_id,
    )

    try:
        db.add(geo)
        db.commit()
        db.refresh(geo)
        return geo
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This vehicle is already assigned to this exact route (start → end).",
        )


def get_geo_constraint(id: int, db: Session) -> models.GeoConstraint:
    geo = (
        db.query(models.GeoConstraint)
        .options(
            joinedload(models.GeoConstraint.start_location),
            joinedload(models.GeoConstraint.end_location),
            joinedload(models.GeoConstraint.vehicle).joinedload(models.Vehicle.constraint),
        )
        .filter(
            models.GeoConstraint.id == id,
            models.GeoConstraint.is_deleted.is_(False),
        )
        .first()
    )
    if not geo:
        raise HTTPException(status_code=404, detail=f"GeoConstraint {id} not found")
    return geo


def all_geo_constraints(
    vehicle_id: Optional[int] = None,
    fleet_id: Optional[int] = None,
    db: Session = None,
) -> list:
    q = (
        db.query(models.GeoConstraint)
        .options(
            joinedload(models.GeoConstraint.start_location),
            joinedload(models.GeoConstraint.end_location),
            joinedload(models.GeoConstraint.vehicle).joinedload(models.Vehicle.constraint),
        )
        .filter(models.GeoConstraint.is_deleted.is_(False))
    )
    if vehicle_id:
        q = q.filter(models.GeoConstraint.vehicle_id == vehicle_id)
    if fleet_id:
        q = q.join(models.Vehicle).filter(models.Vehicle.fleet_id == fleet_id)
    return q.all()


def update_geo_constraint(
    id: int, request: schemas.GeoConstraintUpdate, db: Session
) -> models.GeoConstraint:
    geo = (
        db.query(models.GeoConstraint)
        .filter(
            models.GeoConstraint.id == id,
            models.GeoConstraint.is_deleted.is_(False),
        )
        .first()
    )
    if not geo:
        raise HTTPException(status_code=404, detail=f"GeoConstraint {id} not found")

    if request.start_location_id is not None:
        new_start = _get_location(request.start_location_id, db)
        if new_start.id == geo.end_location_id:
            raise HTTPException(
                status_code=400, detail="Start location cannot be the current end location"
            )
        geo.start_location_id = new_start.id

    if request.end_location_id is not None:
        new_end = _get_location(request.end_location_id, db)
        if new_end.id == geo.start_location_id:
            raise HTTPException(
                status_code=400, detail="End location cannot be the current start location"
            )
        geo.end_location_id = new_end.id

    if request.vehicle_id is not None and request.vehicle_id != geo.vehicle_id:
        vehicle = (
            db.query(models.Vehicle)
            .filter(
                models.Vehicle.id == request.vehicle_id,
                models.Vehicle.is_deleted.is_(False),
            )
            .first()
        )
        if not vehicle:
            raise HTTPException(
                status_code=404, detail=f"Vehicle {request.vehicle_id} not found"
            )
        existing = (
            db.query(models.GeoConstraint)
            .filter(
                models.GeoConstraint.vehicle_id == request.vehicle_id,
                models.GeoConstraint.is_deleted.is_(False),
            )
            .first()
        )
        if existing and existing.id != id:
            raise HTTPException(
                status_code=400, detail="Vehicle already assigned to another geo-constraint"
            )
        geo.vehicle_id = request.vehicle_id

    if request.vehicle_id is None:
        geo.vehicle_id = None

    db.commit()
    db.refresh(geo)
    return geo


def delete_geo_constraint(id: int, db: Session):
    geo = (
        db.query(models.GeoConstraint)
        .filter(
            models.GeoConstraint.id == id,
            models.GeoConstraint.is_deleted.is_(False),
        )
        .first()
    )
    if not geo:
        raise HTTPException(status_code=404, detail=f"GeoConstraint {id} not found")
    geo.soft_delete()
    db.commit()
    return {"message": f"GeoConstraint {id} deleted"}
