from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.database import models
from src.api import schemas

def all_fleets(db: Session):
    try:
        fleets = db.query(models.Fleets).all()
        return fleets
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail=f"unable to load fleets, error: {e}")

def get_fleet(id: int, db: Session):
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == id)
        if not fleet.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"fleet with id {id} not found")
        return fleet.first()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unable to load fleet {id}, error: {e}")

def create_fleet(request: schemas.FleetRequest, db: Session):
    try:
        new_fleet = models.Fleets(
            fleet_name = request.fleet_name,
            type = request.type,
            region = request.region,
            manager = request.manager,
            status = request.status,
            total_vehicles = 0,
            available_vehicles = 0
        )
        db.add(new_fleet)
        db.commit()
        db.refresh(new_fleet)
        return new_fleet
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f'fleet with {request.dict()} not created: {e}')

def delete_fleet(id: int, db: Session):
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == id)
        
        if not fleet.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"fleet with id {id} not found")
        
        fleet.delete(synchronize_session=False)
        db.commit()
        return {f"fleet with id {id} deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unable to delete fleet {id}, error: {e}")


def update_fleet(id: int, request: schemas.FleetRequest, db: Session):
    try:
        fleet = db.query(models.Fleets).filter(models.Fleets.id == id)
        if not fleet.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"fleet with id {id} not found")
        
        fleet.update({
                models.Fleets.fleet_name : request.fleet_name,
                models.Fleets.type : request.type,
                models.Fleets.region : request.region,
                models.Fleets.manager : request.manager,
                models.Fleets.status : request.status
            })
        db.commit()
        return fleet.first()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail= f"unable to update fleet id {id}, error: {e}")