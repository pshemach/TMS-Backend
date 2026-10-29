from pydantic import BaseModel, Field


class DepotBase(BaseModel):
    depot_code: str = Field(description="Unique depot code")
    location: str = Field(description="User prefer location name")
    address: str = Field(description="Address of the depot")
    district: str = Field(description="District belongs to depot")
    latitude: float = Field(ge=5.5, le=10.5, description="Latitude of the depot location")
    longitude: float = Field(ge=78.5, le=82.5, description="Longitude of the depot location")


class DepotRequest(DepotBase):
    """Schema for updating Depot"""
    pass


class DepotResponse(DepotBase):
    id: int
    matrix_status: str
