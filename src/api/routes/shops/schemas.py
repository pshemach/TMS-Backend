from pydantic import BaseModel, Field


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
