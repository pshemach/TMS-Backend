from typing import List, Optional

from pydantic import BaseModel


class LocationInRoute(BaseModel):
    location_id: int


class PredefinedRouteCreate(BaseModel):
    name: str
    locations: List[LocationInRoute]


class PredefinedRouteUpdate(BaseModel):
    name: Optional[str] = None
    locations: Optional[List[LocationInRoute]] = None


class LocationInRouteResponse(BaseModel):
    location_id: int
    location: dict

    class Config:
        from_attributes = True


class PredefinedRouteResponse(BaseModel):
    id: int
    name: str
    locations: List[LocationInRouteResponse] = []

    class Config:
        from_attributes = True
