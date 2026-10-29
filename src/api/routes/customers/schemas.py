from pydantic import BaseModel, Field


class CustomerBase(BaseModel):
    shop_code: str = Field(description="Unique customer code")
    location: str = Field(description="Preferred location name")
    address: str = Field(description="Customer address")
    brand: str = Field(description="Brand")
    district: str = Field(description="District")
    latitude: float = Field(ge=5.5, le=10.5, description="Latitude")
    longitude: float = Field(ge=78.5, le=82.5, description="Longitude")


class CustomerRequest(CustomerBase):
    """Create / update customer."""
    pass


class CustomerResponse(CustomerBase):
    id: int
    matrix_status: str
