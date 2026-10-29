from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.api.deps import get_db
from src.api.routes.customers.repository import location_coords
from src.api.routes.orders import repository as ops
from src.api.routes.orders import schemas
from src.infrastructure.database import models

router = APIRouter(tags=["order"])


def _enrich(order: models.Order) -> schemas.OrderResponse:
    return schemas.OrderResponse(
        id=order.id,
        order_id=order.order_id,
        location_id=order.location_id,
        location=location_coords(order.location),
        po_value=order.po_value,
        volume=order.volume,
        po_date=order.po_date,
        status=order.status.value,
        time_window=schemas.TimeWindow(
            start=order.time_window_start,
            end=order.time_window_end,
        )
        if order.time_window_start
        else None,
        time_window_start=order.time_window_start,
        time_window_end=order.time_window_end,
        priority=order.priority.value if order.priority else None,
        group=None,
    )


@router.post("/order", status_code=status.HTTP_201_CREATED, response_model=schemas.OrderResponse)
def create(request: schemas.OrderCreate, db: Session = Depends(get_db)):
    order = ops.create_order(request, db)
    order = ops.get_order(order.id, db)
    return _enrich(order)


@router.get("/order/{id}", response_model=schemas.OrderResponse)
def get_one(id: int, db: Session = Depends(get_db)):
    return _enrich(ops.get_order(id, db))


@router.get("/order/po/{po_id}", response_model=schemas.OrderResponse)
def get_by_po(po_id: str, db: Session = Depends(get_db)):
    return _enrich(ops.get_order_by_po(po_id, db))


@router.put("/order/{id}", response_model=schemas.OrderResponse)
def update(id: int, request: schemas.OrderUpdate, db: Session = Depends(get_db)):
    ops.update_order(id, request, db)
    return _enrich(ops.get_order(id, db))


@router.put("/order/order_id/{id}", response_model=schemas.OrderResponse)
def update_by_order_id(id: str, request: schemas.OrderUpdate, db: Session = Depends(get_db)):
    order = ops.update_order_oid(id, request, db)
    return _enrich(ops.get_order(order.id, db))


@router.delete("/order/{id}", status_code=status.HTTP_200_OK)
def delete(id: int, db: Session = Depends(get_db)):
    order = ops.get_order(id, db)
    if order.status == models.OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=400, detail=f"Order {order.order_id} has already completed"
        )
    return ops.delete_order(order_db_id=id, db=db)


@router.get("/order", response_model=List[schemas.OrderResponse])
def list_all(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.Order)
        .options(joinedload(models.Order.location))
        .filter(models.Order.is_deleted.is_(False))
    )

    if status:
        if status not in {"pending", "planed", "active", "completed"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        q = q.filter(models.Order.status == models.OrderStatus(status))

    if date_from:
        q = q.filter(models.Order.po_date >= date_from)
    if date_to:
        q = q.filter(models.Order.po_date <= date_to)

    return [_enrich(o) for o in q.all()]
