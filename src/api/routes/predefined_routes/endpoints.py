from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.customers.repository import location_coords
from src.api.routes.predefined_routes import repository as ops
from src.api.routes.predefined_routes import schemas
from src.infrastructure.database import models

router = APIRouter(tags=["predefined-route"])


def _enrich_route(route: models.PredefinedRoute, db: Session) -> schemas.PredefinedRouteResponse:
    enriched = []
    for item in route.locations or []:
        loc_id = item["location_id"]
        loc = (
            db.query(models.Location)
            .filter(models.Location.id == loc_id, models.Location.is_deleted.is_(False))
            .first()
        )
        enriched.append(
            schemas.LocationInRouteResponse(
                location_id=loc_id,
                location=location_coords(loc) if loc else {},
            )
        )
    return schemas.PredefinedRouteResponse(
        id=route.id,
        name=route.name,
        locations=enriched,
    )


@router.post(
    "/predefined-route",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.PredefinedRouteResponse,
)
def create(request: schemas.PredefinedRouteCreate, db: Session = Depends(get_db)):
    route = ops.create_predefined_route(request, db)
    return _enrich_route(route, db)


@router.get("/predefined-route", response_model=List[schemas.PredefinedRouteResponse])
def list_all(db: Session = Depends(get_db)):
    return [_enrich_route(r, db) for r in ops.all_predefined_routes(db)]


@router.get("/predefined-route/{route_id}", response_model=schemas.PredefinedRouteResponse)
def get_one(route_id: int, db: Session = Depends(get_db)):
    return _enrich_route(ops.get_predefined_route(route_id, db), db)


@router.put("/predefined-route/{route_id}", response_model=schemas.PredefinedRouteResponse)
def update(
    route_id: int,
    request: schemas.PredefinedRouteUpdate,
    db: Session = Depends(get_db),
):
    route = ops.update_predefined_route(route_id, request, db)
    return _enrich_route(route, db)


@router.delete("/predefined-route/{route_id}", status_code=status.HTTP_200_OK)
def delete(route_id: int, db: Session = Depends(get_db)):
    return ops.delete_predefined_route(route_id, db)
