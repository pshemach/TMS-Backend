"""Helper module to run optimization synchronously (useful for CLI/tests).

This module provides a small helper function that mirrors the API route's
validation logic but runs the optimization task synchronously instead of
queuing it as a background task.
"""
from typing import List
from sqlalchemy.orm import Session
from src.database import models
from src.core import optimize_routes as opt


def run_optimization_sync(db: Session, request: dict) -> dict:
    """Run optimization synchronously.

    Returns a dict with job_id and status message.
    """
    # Validate vehicles
    selected_vehicles = request.get("selected_vehicles") or []
    if not selected_vehicles:
        return {"error": "No vehicles selected"}

    vehicles: List[models.Vehicles] = db.query(models.Vehicles).filter(
        models.Vehicles.id.in_(selected_vehicles)
    ).all()
    if len(vehicles) != len(selected_vehicles):
        return {"error": "One or more vehicle IDs are invalid"}

    # Resolve orders
    orders = []
    if request.get("order_group_id"):
        group = db.query(models.OrderGroup).filter(models.OrderGroup.id == request["order_group_id"]).first()
        if not group:
            return {"error": "Order group not found"}
        orders = [o for o in group.orders if o.status == models.OrderStatus.PENDING]
    elif request.get("selected_orders"):
        orders = db.query(models.Order).filter(
            models.Order.order_id.in_(request.get("selected_orders")),
            models.Order.status == models.OrderStatus.PENDING
        ).all()
    else:
        return {"error": "Provide selected_orders or order_group_id"}

    if not orders:
        return {"error": "No pending orders to optimize"}

    # Create placeholder job (keeps parity with API behavior)
    job = models.Job(name=f"Delivery {request.get('day')}", day=request.get("day"), status=models.JobStatus.PLANNED)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Run optimizer synchronously
    try:
        opt.run_optimization_task(db, request, vehicles, orders)
        return {"job_id": job.id, "message": "Optimization finished (sync)"}
    except Exception as e:
        return {"job_id": job.id, "error": str(e)}
