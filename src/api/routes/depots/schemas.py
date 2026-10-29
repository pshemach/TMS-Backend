from pydantic import BaseModel, ConfigDict, Field


class DepotBase(BaseModel):
    location_code: str = Field(description="Unique depot code")
    location_name: str = Field(description="Preferred location name")
    address: str = Field(description="Depot address")
    district: str = Field(description="District")
    latitude: float = Field(ge=5.5, le=10.5, description="Latitude")
    longitude: float = Field(ge=78.5, le=82.5, description="Longitude")


class DepotRequest(DepotBase):
    """Create / update depot."""
    pass


class DepotResponse(DepotBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_type: str = "depot"
    matrix_status: str
