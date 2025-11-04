from pydantic import BaseModel, validator, AnyHttpUrl
from typing import Optional, List, Dict
from datetime import date, datetime, time

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
        from_attributes = True

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
        from_attributes = True

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
        from_attributes = True
        
        
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
        from_attributes = True
        
        

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
        
        
class TimeWindow(BaseModel):
    start: Optional[time] = None
    end: Optional[time] = None

    @validator("end")
    def end_after_start(cls, v, values):
        if v and values.get("start") and v <= values["start"]:
            raise ValueError("end time must be after start time")
        return v

class OrderCreate(BaseModel):
    order_id: str
    shop_id: int
    po_value: Optional[float] = None
    volume: Optional[float] = None
    po_date: Optional[date]
    time_window: Optional[TimeWindow] = None
    priority: Optional[str] = None  # "low", "medium", "high"
    
class OrderUpdate(BaseModel):
    order_id: Optional[str] = None
    shop_id: Optional[int] = None
    po_value: Optional[float] = None
    volume: Optional[float] = None
    po_date: Optional[date] = None
    status: Optional[str]
    time_window: Optional[TimeWindow] = None
    priority: Optional[str] = None  # "low", "medium", "high"
    status: Optional[str] = None    # "pending", "active", "completed"

    @validator("priority")
    def validate_priority(cls, v):
        if v and v not in {"low", "medium", "high"}:
            raise ValueError("priority must be low, medium, or high")
        return v

    @validator("status")
    def validate_status(cls, v):
        if v and v not in {"pending", "active", "completed"}:
            raise ValueError("status must be pending, active, or completed")
        return v

class OrderResponse(BaseModel):
    id: int
    order_id: str
    shop_id: int
    shop: dict
    po_value: Optional[float]
    volume: Optional[float]
    po_date: Optional[date]
    status: Optional[str]
    time_window: Optional[TimeWindow]
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None
    priority: Optional[str]
    group: Optional[dict] = None  # {id, name}

    class Config:
        from_attributes = True


# --- Group ---
class OrderGroupCreate(BaseModel):
    name: str
    order_ids: List[str]  # list of `order_id` strings
    
class OrderGroupUpdate(BaseModel):
    name: Optional[str] = None
    order_ids: Optional[List[str]] = None  # list of `order_id` strings

class OrderGroupResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    orders: List[OrderResponse] = []

    class Config:
        from_attributes = True
        
        

class VehicleRouteAssignment(BaseModel):
    vehicle_id: int
    predefined_route_id: Optional[int] = None 
        
class OptimizeRequest(BaseModel):
    day: Optional[date]
    vehicles: List[VehicleRouteAssignment]
    selected_orders: List[int]  # Required: list of order_id strings to optimize
    use_time_windows: Optional[bool] = False

class OptimizeResponse(BaseModel):
    job_id: int
    message: str
    
    

class JobSummary(BaseModel):
    id: int
    name: str
    day: date
    status: str
    created_at: datetime
    route_count: int

class RouteSummary(BaseModel):
    id: int
    vehicle_id: int
    stop_count: int

class JobStopDetail(BaseModel):
    sequence: int
    shop_id: int
    shop_code: str
    shop_coords: dict
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    order_id: Optional[str]
    shop_location: Optional[str]
    shop_address: Optional[str]

class VehicleVisit(BaseModel):
    sequence: int
    shop_id: int
    shop_code: str
    shop_coords: dict

class VehicleRoute(BaseModel):
    id: int
    job_id: int
    vehicle_id: int
    vehicle_name: str
    total_distance: Optional[float]
    total_time: Optional[float]
    folium_html: Optional[str]
    stops: List[JobStopDetail]

class JobResponse(BaseModel):
    id: int
    name: str
    day: date
    status: str
    created_at: datetime
    total_routes: int
    total_stops: int
    routes: List[RouteSummary]