from datetime import date, time
from typing import Optional

from pydantic import BaseModel, validator


class TimeWindow(BaseModel):
    start: Optional[time] = None
    end: Optional[time] = None

    @validator("end")
    def end_after_start(cls, v, values):
        if v and values.get("start") and v <= values["start"]:
            raise ValueError("end time must be after start time")
        return v


class OrderCreate(BaseModel):
    order_id: str
    shop_id: int
    po_value: Optional[float] = None
    volume: Optional[float] = None
    po_date: Optional[date]
    time_window: Optional[TimeWindow] = None
    priority: Optional[str] = None  # "low", "medium", "high"


class OrderUpdate(BaseModel):
    order_id: Optional[str] = None
    shop_id: Optional[int] = None
    po_value: Optional[float] = None
    volume: Optional[float] = None
    po_date: Optional[date] = None
    time_window: Optional[TimeWindow] = None
    priority: Optional[str] = None  # "low", "medium", "high"
    status: Optional[str] = None  # "pending", "active", "completed"

    @validator("priority")
    def validate_priority(cls, v):
        if v and v not in {"low", "medium", "high"}:
            raise ValueError("priority must be low, medium, or high")
        return v

    @validator("status")
    def validate_status(cls, v):
        if v and v not in {"pending", "planed", "active", "completed"}:
            raise ValueError("status must be pending, active, or completed")
        return v


class OrderResponse(BaseModel):
    id: int
    order_id: str
    shop_id: int
    shop: dict
    po_value: Optional[float]
    volume: Optional[float]
    po_date: Optional[date]
    status: Optional[str]
    time_window: Optional[TimeWindow]
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None
    priority: Optional[str]
    group: Optional[dict] = None  # {id, name}

    class Config:
        from_attributes = True
