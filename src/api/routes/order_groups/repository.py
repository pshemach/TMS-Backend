from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from src.infrastructure.database import models
from src.api.routes.order_groups import schemas
from typing import List

# === CREATE (already done) ===
def create_order_group(request: schemas.OrderGroupCreate, db: Session) -> models.OrderGroup:
    if (
        db.query(models.OrderGroup)
        .filter(
            models.OrderGroup.name == request.name,
            models.OrderGroup.is_deleted.is_(False),
        )
        .first()
    ):
        raise HTTPException(400, f"Group name '{request.name}' already exists")

    orders = (
        db.query(models.Order)
        .filter(
            models.Order.order_id.in_(request.order_ids),
            models.Order.is_deleted.is_(False),
        )
        .all()
    )

    if len(orders) != len(request.order_ids):
        raise HTTPException(400, "One or more orders not found or not pending")

    for order in orders:
        if order.group:
            group_name = order.group[0].name if isinstance(order.group, list) else order.group.name
            raise HTTPException(
                400,
                f"Order {order.order_id} is already in group '{group_name}'",
            )
            
            
    group = models.OrderGroup(name=request.name)
    group.orders = orders
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


# === UPDATE GROUP ===
def update_order_group(group_id: int, request: schemas.OrderGroupUpdate, db: Session) -> models.OrderGroup:
    group = (
        db.query(models.OrderGroup)
        .filter(
            models.OrderGroup.id == group_id,
            models.OrderGroup.is_deleted.is_(False),
        )
        .first()
    )
    if not group:
        raise HTTPException(404, "Group not found")

    # Update name
    if request.name and request.name != group.name:
        if (
            db.query(models.OrderGroup)
            .filter(
                models.OrderGroup.name == request.name,
                models.OrderGroup.is_deleted.is_(False),
            )
            .first()
        ):
            raise HTTPException(400, f"Group name '{request.name}' already exists")
        group.name = request.name

    # Update orders (replace all)
    if request.order_ids is not None:
        orders = (
            db.query(models.Order)
            .filter(
                models.Order.order_id.in_(request.order_ids),
                models.Order.is_deleted.is_(False),
            )
            .all()
        )

        if len(orders) != len(request.order_ids):
            raise HTTPException(400, "One or more orders not found or not pending")
        
        # BLOCK: Don't allow order from another group
        for order in orders:
            groups = order.group if isinstance(order.group, list) else ([order.group] if order.group else [])
            other = next((g for g in groups if g.id != group_id), None)
            if other:
                raise HTTPException(
                    400,
                    f"Order {order.order_id} is already in group '{other.name}'",
                )
                
        group.orders = orders  # Replace entire list

    db.commit()
    db.refresh(group)
    return group


# === DELETE GROUP ===
def delete_order_group(group_id: int, db: Session):
    group = (
        db.query(models.OrderGroup)
        .filter(
            models.OrderGroup.id == group_id,
            models.OrderGroup.is_deleted.is_(False),
        )
        .first()
    )
    if not group:
        raise HTTPException(404, "Group not found")

    group.orders = []
    group.soft_delete()
    db.commit()
    return {"message": f"Group {group_id} deleted"}


# === GET GROUP (with orders) ===
def get_order_group(group_id: int, db: Session) -> models.OrderGroup:
    group = (
        db.query(models.OrderGroup)
        .options(joinedload(models.OrderGroup.orders).joinedload(models.Order.location))
        .filter(
            models.OrderGroup.id == group_id,
            models.OrderGroup.is_deleted.is_(False),
        )
        .first()
    )
    if not group:
        raise HTTPException(404, "Group not found")
    return group