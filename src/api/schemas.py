from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict
from datetime import date, datetime, time

# ======== Shop schemas ========
class ShopBase(BaseModel):
    shop_code: str = Field(description="Unique shop code")
    location: str = Field(description="User prefer location name")
    address: str = Field(description="Address of the shop")
    brand: str = Field(description="Brand of the shop")
    district: str = Field(description="District belongs to shop")
    latitude: float = Field(ge=5.5, le=10.5, description="Latitude of the shop location")
    longitude: float = Field(ge=78.5, le=82.5, description="Longitude of the shop location")
    
class ShopRequest(ShopBase):
    """Schema for updating Shop"""
    pass

class ShopResponse(ShopBase):
    id: int
    matrix_status: str
    
    
# ======== Depot schemas ========
class DepotBase(BaseModel):
    depot_code: str = Field(description="Unique depot code")
    location: str = Field(description="User prefer location name")
    address: str = Field(description="Address of the depot")
    district: str = Field(description="District belongs to depot")
    latitude: float = Field(ge=5.5, le=10.5, description="Latitude of the depot location")
    longitude: float = Field(ge=78.5, le=82.5, description="Longitude of the depot location")
    
class DepotRequest(DepotBase):
    """Schema for updating Shop"""
    pass

class DepotResponse(DepotBase):
    id: int
    matrix_status: str


# ======== Fleet schemas ========
class VehicleConstrainBase(BaseModel):
    days: Optional[int] = Field(default=1, description="Number of days vehicle allowed to moves")
    payload: Optional[float] = Field(default=10000.0, description="Payload of the vehicle")
    volume: Optional[float] = Field(default=40.0, description="volume of the vehicle in cubic meters")
    time_window: Optional[str] = Field(default="00:00-23:59")
    max_distance: Optional[float] = Field(default=1200.0, description="max distance allowed for single journey")
    max_visits: Optional[int] = Field(default=15, description="max orders allowed for single journey")

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
    vehicle_name: str = Field(default="Truck 01", description="vehicle name")
    type: str = Field(default="truck", description="Type of the vehicle")
    status: str = Field(default='available', description="Status of the vehicle, this should be available, unavailable, maintenance")
    location: Optional[str] = Field(default="Gampaha", description="Current Location of the vehicle")

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
    fleet_name: Optional[str] = Field(default="Standard Fleet", description="Fleet name")
    type: Optional[str] = Field(default="trucks", description="Type of the fleet")
    region: Optional[str] = Field(default="Island Wide", description="Specific region for fleet")
    manager: Optional[str] = Field(default="Name")
    status: Optional[str] = Field(default="active", description="fleet status")

class FleetRequest(FleetBase):
    """Schema for creating or updating a fleet, with optional fields for partial updates."""
    @validator("status")
    def validate_status(cls, f):
        valid_statuses = ["active", "inactive"]
        if f not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return f

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
        
# ======== Geo constrain schemas ========        
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
        
        
# ======== Predefine route constrain schemas ========
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
        
# ======== Order & constrain schemas ========  
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
        if v and v not in {"pending", "planed", "active", "completed"}:
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
        
        
# ======== Optimization schemas ========
class VehicleRouteAssignment(BaseModel):
    vehicle_id: int
    predefined_route_id: Optional[int] = None 
        
class OptimizeRequest(BaseModel):
    day: Optional[date]
    vehicles: List[VehicleRouteAssignment]
    selected_orders: List[int]  # Required: list of order_id strings to optimize
    depot_id: Optional[int] = None
    use_time_windows: Optional[bool] = False

class OptimizeResponse(BaseModel):
    job_id: int
    message: str
    
    
# ======== Job schemas ========
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