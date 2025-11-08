from sqlalchemy.orm import Session
from src.database import models

def update_job_status(db: Session, job_id: int, new_status: models.JobStatus):
    """Update job status and handle order assignments."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    old_status = job.status
    job.status = new_status
    
    # Get all orders in this job's routes
    order_ids = set()
    for route in job.routes:
        for stop in route.stops:
            if stop.order_id:
                order_ids.add(stop.order_id)
    
    if new_status == models.JobStatus.COMPLETED:
        # Assign job_id and mark orders as COMPLETED
        db.query(models.Order).filter(
            models.Order.order_id.in_(order_ids)
        ).update({
            models.Order.job_id: job_id,
            models.Order.status: models.OrderStatus.COMPLETED
        }, synchronize_session=False)
        
    elif old_status == models.JobStatus.COMPLETED and new_status != models.JobStatus.COMPLETED:
        # If reverting from COMPLETED, clear job_id
        db.query(models.Order).filter(
            models.Order.job_id == job_id
        ).update({
            models.Order.job_id: None,
            models.Order.status: models.OrderStatus.PLANED
        }, synchronize_session=False)
    
    db.commit()
    return job

def delete_job(db: Session, job_id: int) -> dict:
    """Delete a job and reset all its orders to PENDING."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Collect all order_ids from this job's stops
    order_ids = set()
    for route in job.routes:
        for stop in route.stops:
            if stop.order_id:
                order_ids.add(stop.order_id)
    
    print(f"Deleting job {job_id}, resetting {len(order_ids)} orders to PENDING")
    
    # Reset orders that were linked via job_id
    db.query(models.Order).filter(
        models.Order.job_id == job_id
    ).update({
        models.Order.job_id: None,
        models.Order.status: models.OrderStatus.PENDING
    }, synchronize_session=False)
    
    # Reset orders found in stops (by order_id string)
    if order_ids:
        db.query(models.Order).filter(
            models.Order.order_id.in_(order_ids)
        ).update({
            models.Order.job_id: None,
            models.Order.status: models.OrderStatus.PENDING
        }, synchronize_session=False)
    
    # Delete the job (routes and stops will cascade delete)
    db.delete(job)
    db.commit()
    
    return {
        "status": "ok",
        "message": f"Deleted job {job_id} and reset {len(order_ids)} orders to PENDING",
        "reset_orders": list(order_ids)
    }


def cancel_job(db: Session, job_id: int) -> models.Job:
    """Cancel a job and reset orders back to PENDING (keeps job record)."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Get all order_ids from this job's stops
    order_ids = set()
    for route in job.routes:
        for stop in route.stops:
            if stop.order_id:
                order_ids.add(stop.order_id)
    
    print(f"Canceling job {job_id}, resetting {len(order_ids)} orders")
    
    # Reset orders back to PENDING and clear job_id
    db.query(models.Order).filter(
        models.Order.job_id == job_id
    ).update({
        models.Order.job_id: None,
        models.Order.status: models.OrderStatus.PENDING
    }, synchronize_session=False)
    
    if order_ids:
        db.query(models.Order).filter(
            models.Order.order_id.in_(order_ids)
        ).update({
            models.Order.job_id: None,
            models.Order.status: models.OrderStatus.PENDING
        }, synchronize_session=False)
    
    # Update job status (don't delete)
    job.status = models.JobStatus.FAILED  # or add CANCELED status
    
    db.commit()
    db.refresh(job)
    
    return job


def complete_job(db: Session, job_id: int) -> models.Job:
    """Complete a job and assign orders to it."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Get all order_ids from this job's stops
    order_ids = set()
    for route in job.routes:
        for stop in route.stops:
            if stop.order_id:
                order_ids.add(stop.order_id)
    
    print(f"Completing job {job_id}, assigning {len(order_ids)} orders")
    
    # Update orders: assign job_id and mark as COMPLETED
    for order_id in order_ids:
        order = db.query(models.Order).filter(
            models.Order.order_id == order_id
        ).first()
        
        if order:
            order.job_id = job_id  # NOW we assign job_id
            order.status = models.OrderStatus.COMPLETED
            print(f"  Order {order_id}: job_id={job_id}, status=COMPLETED")
    
    # Update job status
    job.status = models.JobStatus.COMPLETED
    
    db.commit()
    db.refresh(job)
    
    return job