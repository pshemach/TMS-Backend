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
    start_location_id: int
    end_location_id: int
    vehicle_id: Optional[int] = None


class GeoConstraintCreate(GeoConstraintBase):
    pass


class GeoConstraintUpdate(BaseModel):
    start_location_id: Optional[int] = None
    end_location_id: Optional[int] = None
    vehicle_id: Optional[int] = None


class GeoConstraintResponse(BaseModel):
    id: int
    start_location: dict
    end_location: dict
    vehicle: Optional[VehicleResponse] = None

    class Config:
        from_attributes = True
