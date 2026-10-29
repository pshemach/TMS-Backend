from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, joinedload

from src.api.deps import get_db
from src.api.routes.customers.repository import location_coords
from src.api.routes.order_groups import repository as ops
from src.api.routes.order_groups import schemas
from src.infrastructure.database import models

router = APIRouter(tags=["order-group"])


def _enrich_order(order: models.Order) -> schemas.OrderResponse:
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
        priority=order.priority.value if order.priority else None,
        group=None,
    )


def _enrich_group(group: models.OrderGroup) -> schemas.OrderGroupResponse:
    return schemas.OrderGroupResponse(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        orders=[_enrich_order(o) for o in group.orders if not o.is_deleted],
    )


@router.post(
    "/order-group",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.OrderGroupResponse,
)
def create(request: schemas.OrderGroupCreate, db: Session = Depends(get_db)):
    group = ops.create_order_group(request, db)
    return _enrich_group(ops.get_order_group(group.id, db))


@router.get("/order-group", response_model=List[schemas.OrderGroupResponse])
def get_all(db: Session = Depends(get_db)):
    groups = (
        db.query(models.OrderGroup)
        .options(joinedload(models.OrderGroup.orders).joinedload(models.Order.location))
        .filter(models.OrderGroup.is_deleted.is_(False))
        .all()
    )
    return [_enrich_group(g) for g in groups]


@router.get("/order-group/{group_id}", response_model=schemas.OrderGroupResponse)
def get_one(group_id: int, db: Session = Depends(get_db)):
    return _enrich_group(ops.get_order_group(group_id, db))


@router.put("/order-group/{group_id}", response_model=schemas.OrderGroupResponse)
def update(group_id: int, request: schemas.OrderGroupUpdate, db: Session = Depends(get_db)):
    group = ops.update_order_group(group_id, request, db)
    return _enrich_group(ops.get_order_group(group.id, db))


@router.delete("/order-group/{group_id}", status_code=status.HTTP_200_OK)
def delete(group_id: int, db: Session = Depends(get_db)):
    return ops.delete_order_group(group_id, db)
