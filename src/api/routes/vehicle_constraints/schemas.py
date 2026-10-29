from typing import Optional

from pydantic import BaseModel, Field, validator


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
