from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional
from src.database import database
from src.database import models
from src.database.repository import geo_constraint_crud as ops
from src.database.repository.shops_curd import shop_coords
from src.api import schemas

get_db = database.get_db

router = APIRouter(prefix="/geo-constraint", tags=["geo-constraint"])


def _enrich(geo: models.GeoConstraint) -> schemas.GeoConstraintResponse:
    """Convert ORM → Pydantic with only needed shop fields."""
    return schemas.GeoConstraintResponse(
        id=geo.id,
        start_shop=shop_coords(geo.start_shop),
        end_shop=shop_coords(geo.end_shop),
        vehicle=geo.vehicle,
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.GeoConstraintResponse)
def create(request: schemas.GeoConstraintCreate, db: Session = Depends(get_db)):
    geo = ops.create_geo_constraint(request, db)
    return _enrich(geo)


@router.get("/", response_model=List[schemas.GeoConstraintResponse])
def list_all(
    vehicle_id: Optional[int] = None,
    fleet_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    geos = ops.all_geo_constraints(vehicle_id=vehicle_id, fleet_id=fleet_id, db=db)
    return [_enrich(g) for g in geos]


@router.get("/{id}", response_model=schemas.GeoConstraintResponse)
def get_one(id: int, db: Session = Depends(get_db)):
    geo = ops.get_geo_constraint(id, db)
    return _enrich(geo)


@router.put("/{id}", response_model=schemas.GeoConstraintResponse)
def update(id: int, request: schemas.GeoConstraintUpdate, db: Session = Depends(get_db)):
    geo = ops.update_geo_constraint(id, request, db)
    return _enrich(geo)


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete(id: int, db: Session = Depends(get_db)):
    return ops.delete_geo_constraint(id, db)