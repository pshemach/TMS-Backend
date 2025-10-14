from pydantic import BaseModel
from typing import Optional

class ShopRequest(BaseModel):
    client: Optional[str]
    shop_code: str
    location: str
    address: str
    brand: str
    district: str
    latitude: float
    longitude: float
    
    
    
    
    
    