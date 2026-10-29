from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from src.api.routes.orders.schemas import OrderResponse


class OrderGroupCreate(BaseModel):
    name: str
    order_ids: List[str]  # list of `order_id` strings


class OrderGroupUpdate(BaseModel):
    name: Optional[str] = None
    order_ids: Optional[List[str]] = None  # list of `order_id` strings


class OrderGroupResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    orders: List[OrderResponse] = []

    class Config:
        from_attributes = True
