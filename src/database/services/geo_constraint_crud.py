from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from src.database import models
from src.api import schemas
from .shops_curd import shop_coords, get_shop   # <-- reuse

# --------------------------------------------------------------
# PRIVATE helpers
# --------------------------------------------------------------
def _get_shop(shop_id: int, db: Session):
    shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")
    return shop

# --------------------------------------------------------------
# PUBLIC CRUD
# --------------------------------------------------------------
def create_geo_constraint(request: schemas.GeoConstraintCreate, db: Session) -> models.GeoConstraint:
    start = _get_shop(request.start_shop_id, db)
    end   = _get_shop(request.end_shop_id, db)

    if start.id == end.id:
        raise HTTPException(status_code=400, detail="Start and end shop must be different")

    # --- BLOCK: only one unassigned route per (start, end) ---
    if request.vehicle_id is None:
        existing_unassigned = db.query(models.GeoConstraint).filter(
            models.GeoConstraint.start_shop_id == start.id,
            models.GeoConstraint.end_shop_id == end.id,
            models.GeoConstraint.vehicle_id.is_(None)
        ).first()
        if existing_unassigned:
            raise HTTPException(
                status_code=400,
                detail="This route (start → end) already exists without a vehicle."
            )

    # --- Validate vehicle if assigned ---
    if request.vehicle_id:
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == request.vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail=f"Vehicle {request.vehicle_id} not found")

    geo = models.GeoConstraint(
        start_shop_id=start.id,
        end_shop_id=end.id,
        vehicle_id=request.vehicle_id,
    )

    try:
        db.add(geo)
        db.commit()
        db.refresh(geo)
        return geo
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This vehicle is already assigned to this exact route (start → end)."
        )
        
def get_geo_constraint(id: int, db: Session) -> models.GeoConstraint:
    geo = (
        db.query(models.GeoConstraint)
        .options(
            joinedload(models.GeoConstraint.start_shop),
            joinedload(models.GeoConstraint.end_shop),
            joinedload(models.GeoConstraint.vehicle).joinedload(models.Vehicles.constraint),
        )
        .filter(models.GeoConstraint.id == id)
        .first()
    )
    if not geo:
        raise HTTPException(status_code=404, detail=f"GeoConstraint {id} not found")
    return geo


def all_geo_constraints(vehicle_id: Optional[int] = None, fleet_id: Optional[int] = None, db: Session = None) -> list[models.GeoConstraint]:
    q = db.query(models.GeoConstraint).options(
        joinedload(models.GeoConstraint.start_shop),
        joinedload(models.GeoConstraint.end_shop),
        joinedload(models.GeoConstraint.vehicle).joinedload(models.Vehicles.constraint),
    )
    if vehicle_id:
        q = q.filter(models.GeoConstraint.vehicle_id == vehicle_id)
    if fleet_id:
        q = q.join(models.Vehicles).filter(models.Vehicles.fleet_id == fleet_id)
    return q.all()


def update_geo_constraint(id: int, request: schemas.GeoConstraintUpdate, db: Session) -> models.GeoConstraint:
    geo = db.query(models.GeoConstraint).filter(models.GeoConstraint.id == id).first()
    if not geo:
        raise HTTPException(status_code=404, detail=f"GeoConstraint {id} not found")

    # ---- start shop -------------------------------------------------
    if request.start_shop_id is not None:
        new_start = _get_shop(request.start_shop_id, db)
        if new_start.id == geo.end_shop_id:
            raise HTTPException(status_code=400, detail="Start shop cannot be the current end shop")
        geo.start_shop_id = new_start.id

    # ---- end shop ---------------------------------------------------
    if request.end_shop_id is not None:
        new_end = _get_shop(request.end_shop_id, db)
        if new_end.id == geo.start_shop_id:
            raise HTTPException(status_code=400, detail="End shop cannot be the current start shop")
        geo.end_shop_id = new_end.id

    # ---- vehicle ----------------------------------------------------
    if request.vehicle_id is not None and request.vehicle_id != geo.vehicle_id:
        vehicle = db.query(models.Vehicles).filter(models.Vehicles.id == request.vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail=f"Vehicle {request.vehicle_id} not found")
        existing = db.query(models.GeoConstraint).filter(models.GeoConstraint.vehicle_id == request.vehicle_id).first()
        if existing and existing.id != id:
            raise HTTPException(status_code=400, detail="Vehicle already assigned to another geo-constraint")
        geo.vehicle_id = request.vehicle_id
        
    if request.vehicle_id is None:
        geo.vehicle_id = None

    db.commit()
    db.refresh(geo)
    return geo


def delete_geo_constraint(id: int, db: Session):
    geo = db.query(models.GeoConstraint).filter(models.GeoConstraint.id == id).first()
    if not geo:
        raise HTTPException(status_code=404, detail=f"GeoConstraint {id} not found")
    db.delete(geo)
    db.commit()
    return {"message": f"GeoConstraint {id} deleted"}