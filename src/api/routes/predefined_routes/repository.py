from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api.routes.predefined_routes import schemas
from src.infrastructure.database import models


def create_predefined_route(
    request: schemas.PredefinedRouteCreate, db: Session
) -> models.PredefinedRoute:
    if (
        db.query(models.PredefinedRoute)
        .filter(
            models.PredefinedRoute.name == request.name,
            models.PredefinedRoute.is_deleted.is_(False),
        )
        .first()
    ):
        raise HTTPException(
            status_code=400, detail=f"Route name '{request.name}' already exists"
        )

    location_ids = [s.location_id for s in request.locations]
    existing = (
        db.query(models.Location.id)
        .filter(
            models.Location.id.in_(location_ids),
            models.Location.is_deleted.is_(False),
        )
        .all()
    )
    existing_ids = {s[0] for s in existing}
    missing = set(location_ids) - existing_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Customers not found: {missing}")

    route = models.PredefinedRoute(
        name=request.name,
        locations=[{"location_id": s.location_id} for s in request.locations],
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


def get_predefined_route(route_id: int, db: Session) -> models.PredefinedRoute:
    route = (
        db.query(models.PredefinedRoute)
        .filter(
            models.PredefinedRoute.id == route_id,
            models.PredefinedRoute.is_deleted.is_(False),
        )
        .first()
    )
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return route


def all_predefined_routes(db: Session):
    return (
        db.query(models.PredefinedRoute)
        .filter(models.PredefinedRoute.is_deleted.is_(False))
        .all()
    )


def update_predefined_route(
    route_id: int, request: schemas.PredefinedRouteUpdate, db: Session
):
    route = get_predefined_route(route_id, db)

    if request.name and request.name != route.name:
        if (
            db.query(models.PredefinedRoute)
            .filter(
                models.PredefinedRoute.name == request.name,
                models.PredefinedRoute.is_deleted.is_(False),
            )
            .first()
        ):
            raise HTTPException(
                status_code=400, detail=f"Route name '{request.name}' already exists"
            )
        route.name = request.name

    if request.locations is not None:
        location_ids = [s.location_id for s in request.locations]
        existing = (
            db.query(models.Location.id)
            .filter(
                models.Location.id.in_(location_ids),
                models.Location.is_deleted.is_(False),
            )
            .all()
        )
        existing_ids = {s[0] for s in existing}
        missing = set(location_ids) - existing_ids
        if missing:
            raise HTTPException(status_code=404, detail=f"Customers not found: {missing}")
        route.locations = [{"location_id": s.location_id} for s in request.locations]

    db.commit()
    db.refresh(route)
    return route


def delete_predefined_route(route_id: int, db: Session):
    route = get_predefined_route(route_id, db)
    route.soft_delete()
    db.commit()
    return {"message": f"Route {route_id} deleted"}
