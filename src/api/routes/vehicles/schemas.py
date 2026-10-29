from typing import Optional

from pydantic import BaseModel, Field, validator

from src.api.routes.vehicle_constraints.schemas import (
    VehicleConstrainRequest,
    VehicleConstrainResponse,
)

__all__ = [
    "VehicleBase",
    "VehicleRequest",
    "VehicleResponse",
    "VehicleConstrainRequest",
    "VehicleConstrainResponse",
]


class VehicleBase(BaseModel):
    vehicle_name: str = Field(default="Truck 01", description="vehicle name")
    type: str = Field(default="truck", description="Type of the vehicle")
    status: str = Field(
        default="available",
        description="Status of the vehicle, this should be available, unavailable, maintenance",
    )
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
