from pydantic import BaseModel, validator
from typing import Optional, List

class ShopRequest(BaseModel):
    shop_code: str
    location: str
    address: str
    brand: str
    district: str
    latitude: float
    longitude: float


class VehicleConstrainBase(BaseModel):
    days: Optional[int] = None
    payload: Optional[float] = None
    volume: Optional[float] = None
    time_window: Optional[str] = None
    max_distance: Optional[float] = None
    max_visits: Optional[int] = None

    @validator("payload", "volume")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Must be positive")
        return v

class VehicleConstrainRequest(VehicleConstrainBase):
    """Schema for updating vehicle constraints."""
    pass

class VehicleConstrainResponse(VehicleConstrainBase):
    """Schema for returning vehicle constraint data."""
    id: int
    vehicle_id: int
    vehicle_name: str
    fleet: str
    type: str

    class Config:
        orm_mode = True

class VehicleBase(BaseModel):
    vehicle_name: str
    type: str
    status: str = 'available'
    location: Optional[str] = None

class VehicleRequest(VehicleBase):
    """Schema for creating or updating a vehicle."""
    
    @validator("status")
    def validate_status(cls, v):
        valid_statuses = ["available", "unavailable", "maintenance"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v

class VehicleResponse(VehicleBase):
    """Schema for returning vehicle data, including constraints."""
    id: int
    fleet_id: int
    constraint: Optional[VehicleConstrainResponse] = None

    class Config:
        orm_mode = True

class FleetBase(BaseModel):
    fleet_name: Optional[str] = None
    type: Optional[str] = None
    region: Optional[str] = None
    manager: Optional[str] = None
    status: Optional[str] = None

class FleetRequest(FleetBase):
    """Schema for creating or updating a fleet, with optional fields for partial updates."""
    pass

class FleetResponse(FleetBase):
    """Schema for returning fleet data, including vehicles."""
    id: int
    fleet_name: str
    type: str
    region: str
    manager: str
    status: str
    total_vehicles: int
    available_vehicles: int
    vehicles: List[VehicleResponse] = []

    class Config:
        orm_mode = True
        
        
class GeoConstraintBase(BaseModel):
    start_shop_id: int
    end_shop_id:   int
    vehicle_id: Optional[int] = None

class GeoConstraintCreate(GeoConstraintBase):
    pass

class GeoConstraintUpdate(BaseModel):
    start_shop_id: Optional[int] = None
    end_shop_id:   Optional[int] = None
    vehicle_id:    Optional[int] = None   # allow clearing

class GeoConstraintResponse(BaseModel):
    id: int
    start_shop: dict          # {shop_code, latitude, longitude}
    end_shop:   dict
    vehicle: Optional[VehicleResponse] = None

    class Config:
        orm_mode = True