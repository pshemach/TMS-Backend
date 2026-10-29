from typing import List, Optional

from pydantic import BaseModel, Field, validator

from src.api.routes.vehicle_constraints.schemas import VehicleConstrainResponse
from src.api.routes.vehicles.schemas import VehicleResponse

__all__ = [
    "FleetBase",
    "FleetRequest",
    "FleetResponse",
    "VehicleResponse",
    "VehicleConstrainResponse",
]


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
