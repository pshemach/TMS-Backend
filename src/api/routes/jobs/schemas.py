from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel


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
    location_id: int
    location_code: str
    location_coords: dict
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    order_id: Optional[str]
    location_name: Optional[str]
    location_address: Optional[str]
    location_type: Optional[str] = None


class VehicleVisit(BaseModel):
    sequence: int
    location_id: int
    location_code: str
    location_coords: dict


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
