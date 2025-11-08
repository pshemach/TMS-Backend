from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from src.database import database
from src.database import models
from src.database.services import predefined_route_crud as ops
from src.api import schemas
from src.database.services.shops_curd import shop_coords

get_db = database.get_db
router = APIRouter(prefix="/predefined-route", tags=["predefined-route"])


def _enrich_route(route: models.PredefinedRoute, db: Session) -> schemas.PredefinedRouteResponse:
    enriched_shops = []
    for shop_data in route.shops:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == shop_data["shop_id"]).first()
        enriched_shops.append(
            schemas.ShopInRouteResponse(
                shop_id=shop_data["shop_id"],
                shop=shop_coords(shop)
            )
        )
    return schemas.PredefinedRouteResponse(
        id=route.id,
        name=route.name,
        shops=enriched_shops
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.PredefinedRouteResponse)
def create(request: schemas.PredefinedRouteCreate, db: Session = Depends(get_db)):
    route = ops.create_predefined_route(request, db)
    return _enrich_route(route, db)


@router.get("/", response_model=List[schemas.PredefinedRouteResponse])
def list_all(db: Session = Depends(get_db)):
    routes = ops.all_predefined_routes(db)
    return [_enrich_route(r, db) for r in routes]


@router.get("/{route_id}", response_model=schemas.PredefinedRouteResponse)
def get_one(route_id: int, db: Session = Depends(get_db)):
    route = ops.get_predefined_route(route_id, db)
    return _enrich_route(route, db)


@router.put("/{route_id}", response_model=schemas.PredefinedRouteResponse)
def update(route_id: int, request: schemas.PredefinedRouteUpdate, db: Session = Depends(get_db)):
    route = ops.update_predefined_route(route_id, request, db)
    return _enrich_route(route, db)


@router.delete("/{route_id}", status_code=status.HTTP_200_OK)
def delete(route_id: int, db: Session = Depends(get_db)):
    return ops.delete_predefined_route(route_id, db)