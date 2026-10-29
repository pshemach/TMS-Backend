from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.customers.repository import location_coords
from src.api.routes.geo_constraints import repository as ops
from src.api.routes.geo_constraints import schemas
from src.infrastructure.database import models

router = APIRouter(tags=["geo-constraint"])


def _enrich(geo: models.GeoConstraint) -> schemas.GeoConstraintResponse:
    vehicle_data = None
    if geo.vehicle:
        vehicle_data = schemas.VehicleResponse.from_orm(geo.vehicle)

    return schemas.GeoConstraintResponse(
        id=geo.id,
        start_location=location_coords(geo.start_location),
        end_location=location_coords(geo.end_location),
        vehicle=vehicle_data,
    )


@router.post(
    "/geo-constraint",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.GeoConstraintResponse,
)
def create(request: schemas.GeoConstraintCreate, db: Session = Depends(get_db)):
    geo = ops.create_geo_constraint(request, db)
    return _enrich(ops.get_geo_constraint(geo.id, db))


@router.get("/geo-constraint", response_model=List[schemas.GeoConstraintResponse])
def list_all(
    vehicle_id: Optional[int] = None,
    fleet_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    geos = ops.all_geo_constraints(vehicle_id=vehicle_id, fleet_id=fleet_id, db=db)
    return [_enrich(g) for g in geos]


@router.get("/geo-constraint/{id}", response_model=schemas.GeoConstraintResponse)
def get_one(id: int, db: Session = Depends(get_db)):
    return _enrich(ops.get_geo_constraint(id, db))


@router.put("/geo-constraint/{id}", response_model=schemas.GeoConstraintResponse)
def update(id: int, request: schemas.GeoConstraintUpdate, db: Session = Depends(get_db)):
    ops.update_geo_constraint(id, request, db)
    return _enrich(ops.get_geo_constraint(id, db))


@router.delete("/geo-constraint/{id}", status_code=status.HTTP_200_OK)
def delete(id: int, db: Session = Depends(get_db)):
    return ops.delete_geo_constraint(id, db)


@router.get(
    "/geo-constraint/by-vehicle/{vehicle_id}",
    response_model=List[schemas.GeoConstraintResponse],
)
def get_by_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    geos = ops.all_geo_constraints(vehicle_id=vehicle_id, db=db)
    return [_enrich(g) for g in geos]
