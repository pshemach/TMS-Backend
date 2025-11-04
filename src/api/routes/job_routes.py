from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date
from src.database import database, models
from src.api import schemas
from src.database.repository.shops_curd import shop_coords
from src.database.repository.order_crud import mark_orders_completed
from src.database.repository import job_curd


router = APIRouter(prefix="/job", tags=["job"])
get_db = database.get_db

# Backwards compatibility: some code expects Vehicles.vehicle_code. Map it to vehicle_name if missing.
if not hasattr(models.Vehicles, "vehicle_code"):
    def _vehicle_code(self):
        return getattr(self, "vehicle_name", None)
    setattr(models.Vehicles, "vehicle_code", property(_vehicle_code))

# === 1. Get Job Summary ===
@router.get("/{job_id}", response_model=schemas.JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).options(
        joinedload(models.Job.routes).joinedload(models.JobRoute.stops).joinedload(models.JobStop.shop)
    ).filter(models.Job.id == job_id).first()

    if not job:
        raise HTTPException(404, "Job not found")

    return _enrich_job(job)


# === 2. List All Jobs ===
@router.get("/", response_model=List[schemas.JobSummary])
def list_jobs(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.Job)
    if status:
        q = q.filter(models.Job.status == status)
    if date_from:
        q = q.filter(models.Job.day >= date_from)
    if date_to:
        q = q.filter(models.Job.day <= date_to)

    jobs = q.order_by(models.Job.created_at.desc()).all()
    return [_summarize_job(j) for j in jobs]


# === 3. Get Visits for Vehicle ===
@router.get("/vehicle/{vehicle_id}/visits", response_model=List[schemas.VehicleVisit])
def get_vehicle_visits(
    vehicle_id: int,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.JobStop).join(models.JobRoute).filter(
        models.JobRoute.vehicle_id == vehicle_id,
        models.JobStop.shop_id != 1  # exclude depot
    )
    if job_id:
        q = q.filter(models.JobRoute.job_id == job_id)

    visits = q.order_by(models.JobStop.sequence).all()

    if not visits:
        raise HTTPException(404, "No visits found for this vehicle")

    return [_enrich_visit(v) for v in visits]


# === 4. Get Full Route for Vehicle ===
@router.get("/vehicle/{vehicle_id}/route", response_model=schemas.VehicleRoute)
def get_vehicle_route(
    vehicle_id: int,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    route = db.query(models.JobRoute).filter(
        models.JobRoute.vehicle_id == vehicle_id
    )
    if job_id:
        route = route.filter(models.JobRoute.job_id == job_id)
    route = route.options(
        joinedload(models.JobRoute.stops).joinedload(models.JobStop.shop),
        joinedload(models.JobRoute.vehicle)
    ).first()

    if not route:
        raise HTTPException(404, "Route not found")

    return _enrich_route(route)


# === 5. Get All Routes in Job ===
@router.get("/{job_id}/routes", response_model=List[schemas.VehicleRoute])
def get_job_routes(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    routes = db.query(models.JobRoute).filter(
        models.JobRoute.job_id == job_id
    ).options(
        joinedload(models.JobRoute.stops).joinedload(models.JobStop.shop),
        joinedload(models.JobRoute.vehicle)
    ).all()

    return [_enrich_route(r) for r in routes]


@router.delete("/{job_id}")
def delete_job_endpoint(
    job_id: int = Path(..., description="Job ID to delete"),
    db: Session = Depends(get_db)
):
    """
    Delete a job and reset all its orders to PENDING.
    
    This will:
    - Delete the job, routes, and stops (cascade)
    - Reset all orders to status=PENDING and job_id=NULL
    """
    try:
        result = job_curd.delete_job(db, job_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{job_id}/complete")
def mark_job_complete(
    job_id: int = Path(..., description="Job ID to complete"),
    db: Session = Depends(get_db)
):
    """Complete a job and assign all its orders."""
    try:
        job = job_curd.complete_job(db, job_id)
        return {
            "status": "ok",
            "message": f"Job {job_id} completed successfully",
            "job_id": job.id,
            "job_status": job.status.value
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{job_id}/cancel")
def mark_job_canceled(
    job_id: int = Path(..., description="Job ID to cancel"),
    db: Session = Depends(get_db)
):
    """Cancel a job and reset its orders (keeps job record)."""
    try:
        job = job_curd.cancel_job(db, job_id)
        return {
            "status": "ok",
            "message": f"Job {job_id} canceled successfully",
            "job_id": job.id,
            "job_status": job.status.value
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# === Helper: Enrich Job ===
def _enrich_job(job: models.Job) -> schemas.JobResponse:
    routes = [_summarize_route(r) for r in job.routes]
    return schemas.JobResponse(
        id=job.id,
        name=job.name,
        day=job.day,
        status=job.status.value,
        created_at=job.created_at,
        total_routes=len(routes),
        total_stops=sum(len(r.stops) for r in job.routes),
        routes=routes
    )


# === Helper: Summarize Job ===
def _summarize_job(job: models.Job) -> schemas.JobSummary:
    return schemas.JobSummary(
        id=job.id,
        name=job.name,
        day=job.day,
        status=job.status.value,
        created_at=job.created_at,
        route_count=len(job.routes)
    )


# === Helper: Enrich Route ===
def _enrich_route(route: models.JobRoute) -> schemas.VehicleRoute:
    stops = [_enrich_stop(s) for s in route.stops if s.shop_id != 1]
    return schemas.VehicleRoute(
        id=route.id,
        job_id=route.job_id,
        vehicle_id=route.vehicle_id,
        vehicle_name=route.vehicle.vehicle_name,
        total_distance=route.total_distance,
        total_time=route.total_time,
        folium_html=route.folium_html,
        stops=stops
    )


# === Helper: Enrich Stop ===
def _enrich_stop(stop: models.JobStop) -> schemas.JobStopDetail:
    shop = stop.shop
    return schemas.JobStopDetail(
        sequence=stop.sequence,
        shop_id=stop.shop_id,
        shop_code=shop.shop_code,
        shop_coords=shop_coords(stop.shop),
        arrival_time=stop.arrival_time,
        departure_time=stop.departure_time,
        order_id=stop.order_id,  
        shop_location=shop.location,  
        shop_address=shop.address  
    )


# === Helper: Enrich Visit (for driver) ===
def _enrich_visit(stop: models.JobStop) -> schemas.VehicleVisit:
    return schemas.VehicleVisit(
        sequence=stop.sequence,
        shop_id=stop.shop_id,
        shop_code=stop.shop.shop_code,
        shop_coords=shop_coords(stop.shop)
    )


# === Helper: Summarize Route ===
def _summarize_route(route: models.JobRoute) -> schemas.RouteSummary:
    return schemas.RouteSummary(
        id=route.id,
        vehicle_id=route.vehicle_id,
        vehicle_code=route.vehicle.vehicle_code,
        stop_count=len([s for s in route.stops if s.shop_id != 1])
    )