from pydantic import BaseModel
from typing import Optional
class ShopRequest(BaseModel):
    shop_code: str
    location: str
    address: str
    brand: str
    district: str
    latitude: float
    longitude: float
    
class FleetRequest(BaseModel):
    fleet_name : str
    type : str
    region : str
    manager : str
    status : str

    
    
    
    
    