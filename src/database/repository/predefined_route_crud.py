from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.database import models
from src.api import schemas
from src.database.repository.shops_curd import shop_coords


def create_predefined_route(request: schemas.PredefinedRouteCreate, db: Session) -> models.PredefinedRoute:
    # Validate name
    if db.query(models.PredefinedRoute).filter(models.PredefinedRoute.name == request.name).first():
        raise HTTPException(status_code=400, detail=f"Route name '{request.name}' already exists")

    # Validate all shops exist
    shop_ids = [s.shop_id for s in request.shops]
    existing_shops = db.query(models.GPSMaster.id).filter(models.GPSMaster.id.in_(shop_ids)).all()
    existing_ids = {s[0] for s in existing_shops}
    missing = set(shop_ids) - existing_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Shops not found: {missing}")

    # Store as list of dicts
    shops_json = [{"shop_id": s.shop_id} for s in request.shops]

    route = models.PredefinedRoute(
        name=request.name,
        shops=shops_json
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


def get_predefined_route(route_id: int, db: Session) -> models.PredefinedRoute:
    route = db.query(models.PredefinedRoute).filter(models.PredefinedRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return route


def all_predefined_routes(db: Session):
    return db.query(models.PredefinedRoute).all()


def update_predefined_route(route_id: int, request: schemas.PredefinedRouteUpdate, db: Session):
    route = db.query(models.PredefinedRoute).filter(models.PredefinedRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    if request.name and request.name != route.name:
        if db.query(models.PredefinedRoute).filter(models.PredefinedRoute.name == request.name).first():
            raise HTTPException(status_code=400, detail=f"Route name '{request.name}' already exists")
        route.name = request.name

    if request.shops is not None:
        shop_ids = [s.shop_id for s in request.shops]
        existing_shops = db.query(models.GPSMaster.id).filter(models.GPSMaster.id.in_(shop_ids)).all()
        existing_ids = {s[0] for s in existing_shops}
        missing = set(shop_ids) - existing_ids
        if missing:
            raise HTTPException(status_code=404, detail=f"Shops not found: {missing}")
        route.shops = [{"shop_id": s.shop_id} for s in request.shops]

    db.commit()
    db.refresh(route)
    return route


def delete_predefined_route(route_id: int, db: Session):
    route = db.query(models.PredefinedRoute).filter(models.PredefinedRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    db.delete(route)
    db.commit()
    return {"message": f"Route {route_id} deleted"}