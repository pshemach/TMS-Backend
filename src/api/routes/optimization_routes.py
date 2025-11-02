from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from src.database import database, models
from datetime import date
from src.api import schemas
from src.core.solver.controller import run_optimization_task

router = APIRouter(prefix="/optimize", tags=["optimization-test"])
get_db = database.get_db

    
@router.post("/")
def run_optimization(
    request: schemas.OptimizeRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
    ):

    if not request.vehicles or len(request.vehicles) == 0:
        raise HTTPException(status_code=400, detail="No vehicles provided in request")
    
    if not request.selected_orders or len(request.selected_orders) == 0:
        raise HTTPException(status_code=400, detail="No orders provided in request")
    
    orders = db.query(models.Order).filter(
		models.Order.id.in_(request.selected_orders),
		models.Order.status != models.OrderStatus.COMPLETED
	).all()
    
    if not orders:
        raise HTTPException(status_code=400, detail="No uncompleted orders found for the provided order IDs")
    
    selected_vehicle_ids = [v.vehicle_id for v in request.vehicles]
    
    vehicles = db.query(models.Vehicles).filter(
		models.Vehicles.id.in_(selected_vehicle_ids)
	).all()
    
    if len(vehicles) != len(selected_vehicle_ids):
        raise HTTPException(status_code=400, detail="One or more vehicle IDs are invalid")    
    
    day = request.day if request.day else date.today()
    
    job =   models.Job(name=f"Delivery {day}", day=day, status=models.JobStatus.RUNNING)  
    db.add(job)
    db.commit()
    db.refresh(job)
    
    background_tasks.add_task(run_optimization_task, db, request, job.id)

    return schemas.OptimizeResponse(
		job_id=job.id,
		message="Optimization started"
	)