from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from src.database import models
from src.api import schemas
from typing import List

# === CREATE (already done) ===
def create_order_group(request: schemas.OrderGroupCreate, db: Session) -> models.OrderGroup:
    if db.query(models.OrderGroup).filter(models.OrderGroup.name == request.name).first():
        raise HTTPException(400, f"Group name '{request.name}' already exists")

    orders = db.query(models.Order).filter(
        models.Order.order_id.in_(request.order_ids)
    ).all()

    if len(orders) != len(request.order_ids):
        raise HTTPException(400, "One or more orders not found or not pending")

    for order in orders:
        if order.group:
            raise HTTPException(
                400,
                f"Order {order.order_id} is already in group '{order.group.name}'"
            )
            
            
    group = models.OrderGroup(name=request.name)
    group.orders = orders
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


# === UPDATE GROUP ===
def update_order_group(group_id: int, request: schemas.OrderGroupUpdate, db: Session) -> models.OrderGroup:
    group = db.query(models.OrderGroup).filter(models.OrderGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Group not found")

    # Update name
    if request.name and request.name != group.name:
        if db.query(models.OrderGroup).filter(models.OrderGroup.name == request.name).first():
            raise HTTPException(400, f"Group name '{request.name}' already exists")
        group.name = request.name

    # Update orders (replace all)
    if request.order_ids is not None:
        # Fetch valid pending orders
        orders = db.query(models.Order).filter(
            models.Order.order_id.in_(request.order_ids)
        ).all()

        if len(orders) != len(request.order_ids):
            raise HTTPException(400, "One or more orders not found or not pending")
        
        # BLOCK: Don't allow order from another group
        for order in orders:
            if order.group and order.group.id != group_id:
                raise HTTPException(
                    400,
                    f"Order {order.order_id} is already in group '{order.group.name}'"
                )
                
        group.orders = orders  # Replace entire list

    db.commit()
    db.refresh(group)
    return group


# === DELETE GROUP ===
def delete_order_group(group_id: int, db: Session):
    group = db.query(models.OrderGroup).filter(models.OrderGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Group not found")

    db.delete(group)
    db.commit()
    return {"message": f"Group {group_id} deleted"}


# === GET GROUP (with orders) ===
def get_order_group(group_id: int, db: Session) -> models.OrderGroup:
    group = db.query(models.OrderGroup).options(
        joinedload(models.OrderGroup.orders).joinedload(models.Order.shop)
    ).filter(models.OrderGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Group not found")
    return group