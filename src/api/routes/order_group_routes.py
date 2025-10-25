from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from src.database import database
from src.database import models
from src.database.repository import order_group_crud as ops
from src.api import schemas
from src.database.repository.shops_curd import shop_coords

get_db = database.get_db
router = APIRouter(prefix="/order-group", tags=["order-group"])


def _enrich_order(order: models.Order) -> schemas.OrderResponse:
    return schemas.OrderResponse(
        id=order.id,
        order_id=order.order_id,
        shop_id=order.shop_id,
        shop=shop_coords(order.shop),
        po_value=order.po_value,
        volume=order.volume,
        po_date=order.po_date,
        status=order.status.value,
        time_window=schemas.TimeWindow(
            start=order.time_window_start,
            end=order.time_window_end
        ) if order.time_window_start else None,
        priority=order.priority.value if order.priority else None,
        group=None  # optional
    )


def _enrich_group(group: models.OrderGroup) -> schemas.OrderGroupResponse:
    return schemas.OrderGroupResponse(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        orders=[_enrich_order(o) for o in group.orders]
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.OrderGroupResponse)
def create(request: schemas.OrderGroupCreate, db: Session = Depends(get_db)):
    group = ops.create_order_group(request, db)
    return _enrich_group(group)


@router.get("/{group_id}", response_model=schemas.OrderGroupResponse)
def get(group_id: int, db: Session = Depends(get_db)):
    group = ops.get_order_group(group_id, db)
    return _enrich_group(group)


@router.put("/{group_id}", response_model=schemas.OrderGroupResponse)
def update(group_id: int, request: schemas.OrderGroupUpdate, db: Session = Depends(get_db)):
    group = ops.update_order_group(group_id, request, db)
    return _enrich_group(group)


@router.delete("/{group_id}", status_code=status.HTTP_200_OK)
def delete(group_id: int, db: Session = Depends(get_db)):
    return ops.delete_order_group(group_id, db)