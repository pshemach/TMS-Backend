from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from src.database import database, models
from src.api import schemas
from src.core import optimize_routes as opt

router = APIRouter(prefix="/optimize", tags=["optimization"])
get_db = database.get_db


@router.post("/", response_model=schemas.OptimizeResponse)
def run_optimization(
	request: schemas.OptimizeRequest,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db)
):
	"""Start an optimization job in background.

	Validations:
	- selected_vehicles must exist
	- either selected_orders or order_group_id must be provided
	- only pending orders are considered
	"""
	# Extract vehicle ids and optional predefined route ids from the new schema
	if not request.vehicles or len(request.vehicles) == 0:
		raise HTTPException(status_code=400, detail="No vehicles provided in request")

	selected_vehicle_ids = [v.vehicle_id for v in request.vehicles]
	predefined_route_ids = [v.predefined_route_id for v in request.vehicles if v.predefined_route_id]

	vehicles: List[models.Vehicles] = db.query(models.Vehicles).filter(
		models.Vehicles.id.in_(selected_vehicle_ids)
	).all()
	if len(vehicles) != len(selected_vehicle_ids):
		raise HTTPException(status_code=400, detail="One or more vehicle IDs are invalid")

	# Resolve orders
	orders = []
	if request.order_group_id:
		group = db.query(models.OrderGroup).filter(models.OrderGroup.id == request.order_group_id).first()
		if not group:
			raise HTTPException(status_code=404, detail="Order group not found")
		orders = [o for o in group.orders if o.status == models.OrderStatus.PENDING]
	elif request.selected_orders:
		orders = db.query(models.Order).filter(
			models.Order.order_id.in_(request.selected_orders),
			models.Order.status == models.OrderStatus.PENDING
		).all()
	else:
		raise HTTPException(status_code=400, detail="Provide selected_orders or order_group_id")

	if not orders:
		raise HTTPException(status_code=400, detail="No pending orders to optimize")

	# Create job placeholder
	job = models.Job(name=f"Delivery {request.day}", day=request.day, status=models.JobStatus.PLANNED)
	db.add(job)
	db.commit()
	db.refresh(job)

	# Build payload shape expected by core optimizer and queue background worker
	request_payload = {
		"day": request.day,
		"selected_vehicles": selected_vehicle_ids,
		"selected_orders": request.selected_orders,
		"order_group_id": request.order_group_id,
		"predefined_route_ids": predefined_route_ids or None,
		"use_time_windows": request.use_time_windows,
		"priority_orders": request.priority_orders or [],
		"geo_constraints": request.geo_constraints or [],
	}

	# Queue background worker (pass job id so core updates the placeholder)
	background_tasks.add_task(opt.run_optimization_task, db, request_payload, vehicles, orders, job.id)

	return schemas.OptimizeResponse(
		job_id=job.id,
		message="Optimization started",
		fixed_routes=0,
		optimized_routes=0,
		total_shops=len(orders)
	)


@router.get("/job/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
	"""Return basic job status and counts."""
	job = db.query(models.Job).filter(models.Job.id == job_id).first()
	if not job:
		raise HTTPException(status_code=404, detail="Job not found")

	route_count = db.query(models.JobRoute).filter(models.JobRoute.job_id == job_id).count()
	stop_count = db.query(models.JobStop).join(models.JobRoute).filter(models.JobRoute.job_id == job_id).count()

	return {
		"id": job.id,
		"name": job.name,
		"day": job.day,
		"status": job.status.value,
		"created_at": job.created_at,
		"route_count": route_count,
		"stop_count": stop_count,
	}
