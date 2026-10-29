from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    location_code: str = Field(description="Unique customer code")
    location_name: str = Field(description="Preferred location name")
    address: str = Field(description="Customer address")
    brand: str = Field(description="Brand")
    district: str = Field(description="District")
    latitude: float = Field(ge=5.5, le=10.5, description="Latitude")
    longitude: float = Field(ge=78.5, le=82.5, description="Longitude")


class CustomerRequest(CustomerBase):
    """Create / update customer."""
    pass


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_type: str = "customer"
    matrix_status: str
