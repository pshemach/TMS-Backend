from typing import List, Optional

from pydantic import BaseModel


class ShopInRoute(BaseModel):
    shop_id: int


class PredefinedRouteCreate(BaseModel):
    name: str
    shops: List[ShopInRoute]  # list of shop IDs


class PredefinedRouteUpdate(BaseModel):
    name: Optional[str] = None
    shops: Optional[List[ShopInRoute]] = None


class ShopInRouteResponse(BaseModel):
    shop_id: int
    shop: dict  # {shop_code, latitude, longitude}

    class Config:
        from_attributes = True


class PredefinedRouteResponse(BaseModel):
    id: int
    name: str
    shops: List[ShopInRouteResponse] = []

    class Config:
        from_attributes = True
