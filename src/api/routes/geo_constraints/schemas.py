from typing import Optional

from pydantic import BaseModel

from src.api.routes.vehicles.schemas import VehicleResponse

__all__ = [
    "GeoConstraintBase",
    "GeoConstraintCreate",
    "GeoConstraintUpdate",
    "GeoConstraintResponse",
    "VehicleResponse",
]


class GeoConstraintBase(BaseModel):
    start_shop_id: int
    end_shop_id: int
    vehicle_id: Optional[int] = None


class GeoConstraintCreate(GeoConstraintBase):
    pass


class GeoConstraintUpdate(BaseModel):
    start_shop_id: Optional[int] = None
    end_shop_id: Optional[int] = None
    vehicle_id: Optional[int] = None  # allow clearing


class GeoConstraintResponse(BaseModel):
    id: int
    start_shop: dict  # {shop_code, latitude, longitude}
    end_shop: dict
    vehicle: Optional[VehicleResponse] = None

    class Config:
        from_attributes = True
