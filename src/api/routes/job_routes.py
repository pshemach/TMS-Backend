from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date
from src.database import database, models
from src.api import schemas
from src.database.repository.shops_curd import shop_coords

router = APIRouter(prefix="/job", tags=["job"])
get_db = database.get_db

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
        vehicle_code=route.vehicle.vehicle_code,
        total_distance=route.total_distance,
        total_time=route.total_time,
        stops=stops
    )


# === Helper: Enrich Stop ===
def _enrich_stop(stop: models.JobStop) -> schemas.JobStopDetail:
    return schemas.JobStopDetail(
        sequence=stop.sequence,
        shop_id=stop.shop_id,
        shop_code=stop.shop.shop_code,
        shop_coords=shop_coords(stop.shop),
        arrival_time=stop.arrival_time,
        departure_time=stop.departure_time
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