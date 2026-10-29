from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session, joinedload

from src.api.deps import get_db
from src.api.routes.customers.repository import location_coords
from src.api.routes.jobs import repository as job_curd
from src.api.routes.jobs import schemas
from src.infrastructure.database import models

router = APIRouter(tags=["job"])

if not hasattr(models.Vehicle, "vehicle_code"):
    def _vehicle_code(self):
        return getattr(self, "vehicle_name", None)

    setattr(models.Vehicle, "vehicle_code", property(_vehicle_code))


def _is_customer_stop(stop: models.JobStop) -> bool:
    loc = stop.location
    if not loc:
        return False
    return loc.location_type == models.LocationType.CUSTOMER


@router.get("/job", response_model=List[schemas.JobSummary])
def list_jobs(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.Job)
        .options(joinedload(models.Job.routes))
        .filter(models.Job.is_deleted.is_(False))
    )
    if status:
        try:
            q = q.filter(models.Job.status == models.JobStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job status")
    if date_from:
        q = q.filter(models.Job.day >= date_from)
    if date_to:
        q = q.filter(models.Job.day <= date_to)

    jobs = q.order_by(models.Job.created_at.desc()).all()
    return [_summarize_job(j) for j in jobs]


@router.get("/job/{job_id}", response_model=schemas.JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = (
        db.query(models.Job)
        .options(
            joinedload(models.Job.routes)
            .joinedload(models.JobRoute.stops)
            .joinedload(models.JobStop.location)
        )
        .filter(models.Job.id == job_id, models.Job.is_deleted.is_(False))
        .first()
    )
    if not job:
        raise HTTPException(404, "Job not found")
    return _enrich_job(job)


@router.get("/job/vehicle/{vehicle_id}/visits", response_model=List[schemas.VehicleVisit])
def get_vehicle_visits(
    vehicle_id: int,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.JobStop)
        .join(models.JobRoute)
        .join(models.Location)
        .filter(
            models.JobRoute.vehicle_id == vehicle_id,
            models.Location.location_type == models.LocationType.CUSTOMER,
            models.Location.is_deleted.is_(False),
        )
    )
    if job_id:
        q = q.filter(models.JobRoute.job_id == job_id)

    visits = q.order_by(models.JobStop.sequence).all()
    if not visits:
        raise HTTPException(404, "No visits found for this vehicle")
    return [_enrich_visit(v) for v in visits]


@router.get("/job/vehicle/{vehicle_id}/route", response_model=schemas.VehicleRoute)
def get_vehicle_route(
    vehicle_id: int,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    route_q = db.query(models.JobRoute).filter(models.JobRoute.vehicle_id == vehicle_id)
    if job_id:
        route_q = route_q.filter(models.JobRoute.job_id == job_id)
    route = route_q.options(
        joinedload(models.JobRoute.stops).joinedload(models.JobStop.location),
        joinedload(models.JobRoute.vehicle),
    ).first()
    if not route:
        raise HTTPException(404, "Route not found")
    return _enrich_route(route)


@router.get("/job/{job_id}/routes", response_model=List[schemas.VehicleRoute])
def get_job_routes(job_id: int, db: Session = Depends(get_db)):
    job = (
        db.query(models.Job)
        .filter(models.Job.id == job_id, models.Job.is_deleted.is_(False))
        .first()
    )
    if not job:
        raise HTTPException(404, "Job not found")

    routes = (
        db.query(models.JobRoute)
        .filter(models.JobRoute.job_id == job_id)
        .options(
            joinedload(models.JobRoute.stops).joinedload(models.JobStop.location),
            joinedload(models.JobRoute.vehicle),
        )
        .all()
    )
    return [_enrich_route(r) for r in routes]


@router.delete("/job/{job_id}")
def delete_job_endpoint(
    job_id: int = Path(..., description="Job ID to delete"),
    db: Session = Depends(get_db),
):
    try:
        return job_curd.delete_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/job/{job_id}/complete")
def mark_job_complete(
    job_id: int = Path(..., description="Job ID to complete"),
    db: Session = Depends(get_db),
):
    try:
        job = job_curd.complete_job(db, job_id)
        return {
            "status": "ok",
            "message": f"Job {job_id} completed successfully",
            "job_id": job.id,
            "job_status": job.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/job/{job_id}/cancel")
def mark_job_canceled(
    job_id: int = Path(..., description="Job ID to cancel"),
    db: Session = Depends(get_db),
):
    try:
        job = job_curd.cancel_job(db, job_id)
        return {
            "status": "ok",
            "message": f"Job {job_id} canceled successfully",
            "job_id": job.id,
            "job_status": job.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _enrich_job(job: models.Job) -> schemas.JobResponse:
    routes = [_summarize_route(r) for r in job.routes]
    return schemas.JobResponse(
        id=job.id,
        name=job.name,
        day=job.day,
        status=job.status.value,
        created_at=job.created_at,
        total_routes=len(routes),
        total_stops=sum(r.stop_count for r in routes),
        routes=routes,
    )


def _summarize_job(job: models.Job) -> schemas.JobSummary:
    return schemas.JobSummary(
        id=job.id,
        name=job.name,
        day=job.day,
        status=job.status.value,
        created_at=job.created_at,
        route_count=len(job.routes),
    )


def _enrich_route(route: models.JobRoute) -> schemas.VehicleRoute:
    # Include depot + customer stops so Visualization can show the full path
    stops = [_enrich_stop(s) for s in route.stops if s.location and not s.location.is_deleted]
    return schemas.VehicleRoute(
        id=route.id,
        job_id=route.job_id,
        vehicle_id=route.vehicle_id,
        vehicle_name=route.vehicle.vehicle_name,
        total_distance=route.total_distance,
        total_time=route.total_time,
        folium_html=route.folium_html,
        stops=stops,
    )


def _enrich_stop(stop: models.JobStop) -> schemas.JobStopDetail:
    loc = stop.location
    loc_type = (
        loc.location_type.value
        if hasattr(loc.location_type, "value")
        else str(loc.location_type)
    )
    return schemas.JobStopDetail(
        sequence=stop.sequence,
        location_id=stop.location_id,
        location_code=loc.location_code,
        location_coords=location_coords(loc),
        arrival_time=stop.arrival_time,
        departure_time=stop.departure_time,
        order_id=stop.order_id,
        location_name=loc.location_name,
        location_address=loc.address,
        location_type=loc_type.lower() if loc_type else None,
    )


def _enrich_visit(stop: models.JobStop) -> schemas.VehicleVisit:
    return schemas.VehicleVisit(
        sequence=stop.sequence,
        location_id=stop.location_id,
        location_code=stop.location.location_code,
        location_coords=location_coords(stop.location),
    )


def _summarize_route(route: models.JobRoute) -> schemas.RouteSummary:
    return schemas.RouteSummary(
        id=route.id,
        vehicle_id=route.vehicle_id,
        stop_count=len([s for s in route.stops if _is_customer_stop(s)]),
    )


# Keep customer-only visit list for drivers; full route includes depot for maps.
