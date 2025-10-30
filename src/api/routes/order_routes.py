from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from src.database import database
from src.database import models
from src.database.repository import order_crud as ops
from src.api import schemas
from src.database.repository.shops_curd import shop_coords
from datetime import date

get_db = database.get_db
router = APIRouter(prefix="/order", tags=["order"])


def _enrich(order: models.Order) -> schemas.OrderResponse:
    return schemas.OrderResponse(
        id=order.id,
        order_id=order.order_id,
        shop_id=order.shop_id,
        shop=shop_coords(order.shop),
        po_value=order.po_value,
        volume=order.volume,
        po_date=order.po_date,
        status=order.status.value,  # ← "pending", "active", "completed"
        time_window=schemas.TimeWindow(
            start=order.time_window_start,
            end=order.time_window_end
        ) if order.time_window_start else None,
        time_window_start = order.time_window_start if order.time_window_start else None,
        time_window_end = order.time_window_end if order.time_window_end else None,
        priority=order.priority.value if order.priority else None,
        group=None  # optional
    )

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.OrderResponse)
def create(request: schemas.OrderCreate, db: Session = Depends(get_db)):
    order = ops.create_order(request, db)
    return _enrich(order)


# @router.get("/", response_model=List[schemas.OrderResponse])
# def list_all(
#     shop_id: Optional[int] = None,
#     date_from: Optional[date] = None,
#     date_to: Optional[date] = None,
#     db: Session = Depends(get_db)
# ):
#     orders = ops.all_orders(db, shop_id, date_from, date_to)
#     return [_enrich(o) for o in orders]


@router.get("/{id}", response_model=schemas.OrderResponse)
def get_one(id: int, db: Session = Depends(get_db)):
    order = ops.get_order(id, db)
    return _enrich(order)


@router.get("/po/{po_id}", response_model=schemas.OrderResponse)
def get_by_po(po_id: str, db: Session = Depends(get_db)):
    order = ops.get_order_by_po(po_id, db)
    return _enrich(order)


@router.put("/{id}", response_model=schemas.OrderResponse)
def update(id: int, request: schemas.OrderUpdate, db: Session = Depends(get_db)):
    order = ops.update_order(id, request, db)
    return _enrich(order)

@router.put("/order_id/{id}", response_model=schemas.OrderResponse)
def update(id: str, request: schemas.OrderUpdate, db: Session = Depends(get_db)):
    order = ops.update_order_oid(id, request, db)
    return _enrich(order)

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete(id: int, db: Session = Depends(get_db)):
    return ops.delete_order(id, db)

@router.get("/", response_model=List[schemas.OrderResponse])
def list_all(
    status: Optional[str] = None,           # filter by status
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.Order).options(joinedload(models.Order.shop))
    
    if status:
        if status not in {"pending", "active", "completed"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        q = q.filter(models.Order.status == models.OrderStatus(status))
    
    if date_from:
        q = q.filter(models.Order.po_date >= date_from)
    if date_to:
        q = q.filter(models.Order.po_date <= date_to)
    
    orders = q.all()
    return [_enrich(o) for o in orders]