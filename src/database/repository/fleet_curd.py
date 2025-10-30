from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from src.database import models
from src.api import schemas

def all_fleets(db: Session):
    """Retrieve all fleets from the database."""
    try:
        fleets = db.query(models.Fleets).options(joinedload(models.Fleets.vehicles).joinedload(models.Vehicles.constraint)).all()
        return fleets
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load fleets, error: {e}"
        )
        
def get_fleet(id: int, db: Session):
    """Retrieve a fleet by ID."""
    try:
        fleet = fleet = db.query(models.Fleets).options(joinedload(models.Fleets.vehicles).joinedload(models.Vehicles.constraint)).filter(models.Fleets.id == id).first()
        if not fleet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {id} not found"
            )
        return fleet
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load fleet {id}, error: {e}"
        )

def create_fleet(request: schemas.FleetRequest, db: Session):
    """Create a new fleet."""
    try:
        # Ensure all required fields are provided for creation
        if not all([request.fleet_name, request.type, request.region, request.manager, request.status]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All fields (fleet_name, type, region, manager, status) are required for creating a fleet"
            )
        new_fleet = models.Fleets(
            fleet_name=request.fleet_name,
            type=request.type,
            region=request.region,
            manager=request.manager,
            status=request.status,
            total_vehicles=0,
            available_vehicles=0
        )
        db.add(new_fleet)
        db.commit()
        db.refresh(new_fleet)
        return new_fleet
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Fleet with {request.dict()} not created: {e}"
        )
        
def delete_fleet(id: int, db: Session):
    """Delete a fleet by ID."""
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == id).first()
        if not fleet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {id} not found"
            )
        db.delete(fleet)
        db.commit()
        return {"message": f"Fleet with id {id} deleted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete fleet {id}, error: {e}"
        )

def update_fleet(id: int, request: schemas.FleetRequest, db: Session):
    """Update fleet metadata (excludes vehicle counts)."""
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == id)
        if not fleet.first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet with id {id} not found"
            )
        
        update_data = {}
        if request.fleet_name is not None:
            update_data[models.Fleets.fleet_name] = request.fleet_name
        if request.type is not None:
            update_data[models.Fleets.type] = request.type
        if request.region is not None:
            update_data[models.Fleets.region] = request.region
        if request.manager is not None:
            update_data[models.Fleets.manager] = request.manager
        if request.status is not None:
            update_data[models.Fleets.status] = request.status
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )
        
        fleet.update(update_data)
        db.commit()
        updated_fleet = fleet.first()
        db.refresh(updated_fleet)
        return updated_fleet
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update fleet id {id}, error: {e}"
        )