from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from src.database import database, models
from src.core import optimize_routes as opt
from datetime import date
from pydantic import BaseModel

router = APIRouter(prefix="/optimize-test", tags=["optimization-test"])
get_db = database.get_db

class OptimizeResponse(BaseModel):
    job_id: int
    message: str
    fixed_routes: int
    optimized_routes: int
    total_shops: int

class VehicleRouteAssignment(BaseModel):
    vehicle_id: int
    predefined_route_id: Optional[int] = None 
    
class OptimizeRequest(BaseModel):
    day: Optional[date]
    vehicles: Optional[List[VehicleRouteAssignment]]
    selected_order_id: Optional[List[int]] = None
    order_group_id: Optional[List[int]] = None
    use_time_windows: Optional[bool] = False
    
@router.post("/", response_model=OptimizeResponse)
def run_optimization(request: OptimizeRequest, background_tasks: BackgroundTasks,db: Session = Depends(get_db)):
    # Extract vehicle ids and optional predefined route ids from the new schema
    print(request.vehicles)
    if not request.vehicles or len(request.vehicles) == 0:
        raise HTTPException(status_code=400, detail="No vehicles provided in request")
    
    if not request.selected_order_id or len(request.selected_order_id) == 0:
        raise HTTPException(status_code=400, detail="No orders provided in request")
    
    orders = db.query(models.Order).filter(
			models.Order.id.in_(request.selected_order_id)
		).all()
    
    if not orders:
        raise HTTPException(status_code=400, detail="No pending orders to optimize")

    orders_lis = [order.shop_id for order in orders]
    
    print(orders_lis)

    
    return request