from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class VehicleRouteAssignment(BaseModel):
    vehicle_id: int
    predefined_route_id: Optional[int] = None


class OptimizeRequest(BaseModel):
    day: Optional[date]
    vehicles: List[VehicleRouteAssignment]
    selected_orders: List[int]  # Required: list of order IDs to optimize
    depot_id: Optional[int] = None
    use_time_windows: Optional[bool] = False


class OptimizeResponse(BaseModel):
    job_id: int
    message: str
