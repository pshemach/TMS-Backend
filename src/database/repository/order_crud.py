from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from src.database import models
from src.api import schemas
from src.database.repository.shops_curd import shop_coords
from src.database.models import OrderStatus, Priority
from datetime import date
from typing import List

def create_order(request: schemas.OrderCreate, db: Session) -> models.Order:
    # Validate shop exists
    shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == request.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop {request.shop_id} not found")

    # Validate unique order_id
    if db.query(models.Order).filter(models.Order.order_id == request.order_id).first():
        raise HTTPException(status_code=400, detail=f"Order ID {request.order_id} already exists")

    order = models.Order(
        order_id=request.order_id,
        shop_id=request.shop_id,
        po_value=request.po_value,
        volume=request.volume,
        po_date=request.po_date,
        status=OrderStatus.PENDING,  # default
        time_window_start=request.time_window.start if request.time_window else None,
        time_window_end=request.time_window.end if request.time_window else None,
        priority=Priority(request.priority) if request.priority else Priority.MEDIUM,
        
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(order_db_id: int, db: Session) -> models.Order:
    order = db.query(models.Order).options(joinedload(models.Order.shop)).filter(models.Order.id == order_db_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_db_id} not found")
    return order

def get_pending_orders(db: Session, date_from: date = None, date_to: date = None):
    q = db.query(models.Order).options(joinedload(models.Order.shop)).filter(
        models.Order.status == OrderStatus.PENDING
    )
    if date_from:
        q = q.filter(models.Order.po_date >= date_from)
    if date_to:
        q = q.filter(models.Order.po_date <= date_to)
    return q.all()

def get_order_by_po(po_id: str, db: Session) -> models.Order:
    order = db.query(models.Order).options(joinedload(models.Order.shop)).filter(models.Order.order_id == po_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {po_id} not found")
    return order


def all_orders(db: Session, shop_id: int = None, date_from: date = None, date_to: date = None):
    q = db.query(models.Order).options(joinedload(models.Order.shop))
    if shop_id:
        q = q.filter(models.Order.shop_id == shop_id)
    if date_from:
        q = q.filter(models.Order.po_date >= date_from)
    if date_to:
        q = q.filter(models.Order.po_date <= date_to)
    return q.all()

    
def update_order(order_db_id: int, request: schemas.OrderUpdate, db: Session) -> models.Order:
    order = db.query(models.Order).filter(models.Order.id == order_db_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_db_id} not found")

    # === Validate & Update order_id ===
    if request.order_id and request.order_id != order.order_id:
        if db.query(models.Order).filter(models.Order.order_id == request.order_id).first():
            raise HTTPException(400, f"Order ID {request.order_id} already exists")
        order.order_id = request.order_id

    # === Validate & Update shop_id ===
    if request.shop_id and request.shop_id != order.shop_id:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == request.shop_id).first()
        if not shop:
            raise HTTPException(404, f"Shop {request.shop_id} not found")
        order.shop_id = request.shop_id

    # === Simple fields ===
    if request.po_value is not None:
        order.po_value = request.po_value
    if request.volume is not None:
        order.volume = request.volume
    if request.po_date:
        order.po_date = request.po_date

    # === Time Window ===
    if request.time_window is not None:
        order.time_window_start = request.time_window.start
        order.time_window_end = request.time_window.end
    # Allow clearing time window
    elif request.time_window is None and (order.time_window_start or order.time_window_end):
        order.time_window_start = None
        order.time_window_end = None

    # === Priority ===
    if request.priority:
        order.priority = Priority(request.priority)
    elif request.priority is None and order.priority:
        order.priority = Priority.MEDIUM  # default

    # === Status (with validation) ===
    if request.status:
        new_status = OrderStatus(request.status)
        # Optional: Prevent invalid transitions
        if order.status == OrderStatus.COMPLETED and new_status != OrderStatus.COMPLETED:
            raise HTTPException(400, "Cannot change status from completed")
        if order.status == OrderStatus.ACTIVE and new_status == OrderStatus.PENDING:
            raise HTTPException(400, "Cannot revert active to pending")
        order.status = new_status

    db.commit()
    db.refresh(order)
    return order

def update_order_oid(order_db_id: str, request: schemas.OrderUpdate, db: Session) -> models.Order:
    order = db.query(models.Order).filter(models.Order.order_id == order_db_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_db_id} not found")

    # === Validate & Update order_id ===
    if request.order_id and request.order_id != order.order_id:
        if db.query(models.Order).filter(models.Order.order_id == request.order_id).first():
            raise HTTPException(400, f"Order ID {request.order_id} already exists")
        order.order_id = request.order_id

    # === Validate & Update shop_id ===
    if request.shop_id and request.shop_id != order.shop_id:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == request.shop_id).first()
        if not shop:
            raise HTTPException(404, f"Shop {request.shop_id} not found")
        order.shop_id = request.shop_id

    # === Simple fields ===
    if request.po_value is not None:
        order.po_value = request.po_value
    if request.volume is not None:
        order.volume = request.volume
    if request.po_date:
        order.po_date = request.po_date

    # === Time Window ===
    if request.time_window is not None:
        order.time_window_start = request.time_window.start
        order.time_window_end = request.time_window.end
    # Allow clearing time window
    elif request.time_window is None and (order.time_window_start or order.time_window_end):
        order.time_window_start = None
        order.time_window_end = None

    # === Priority ===
    if request.priority:
        order.priority = Priority(request.priority)
    elif request.priority is None and order.priority:
        order.priority = Priority.MEDIUM  # default

    # === Status (with validation) ===
    if request.status:
        new_status = OrderStatus(request.status)
        # Optional: Prevent invalid transitions
        if order.status == OrderStatus.COMPLETED and new_status != OrderStatus.COMPLETED:
            raise HTTPException(400, "Cannot change status from completed")
        if order.status == OrderStatus.ACTIVE and new_status == OrderStatus.PENDING:
            raise HTTPException(400, "Cannot revert active to pending")
        order.status = new_status

    db.commit()
    db.refresh(order)
    return order

def delete_order(order_db_id: int, db: Session):
    order = db.query(models.Order).filter(models.Order.id == order_db_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_db_id} not found")
    db.delete(order)
    db.commit()
    return {"message": f"Order {order_db_id} deleted"}

def mark_orders_active(order_ids: List[int], db: Session):
    db.query(models.Order).filter(
        models.Order.id.in_(order_ids),
        models.Order.status == OrderStatus.PENDING
    ).update({models.Order.status: OrderStatus.ACTIVE}, synchronize_session=False)
    db.commit()

def mark_orders_completed(order_ids: List[int], db: Session):
    db.query(models.Order).filter(
        models.Order.id.in_(order_ids)
    ).update({models.Order.status: OrderStatus.COMPLETED}, synchronize_session=False)
    db.commit()