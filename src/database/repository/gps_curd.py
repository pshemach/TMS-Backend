from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.database import models
from src.api import schemas


def get_all(db: Session):
    try:
        shops = db.query(models.GPSMaster).all()
        return shops
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail=f"unable to load shops, error: {e}")

def get_shop(id: int, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == id)
        if not shop.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"shop with id {id} not found")
        return shop.first()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unable to load shop {id}, error: {e}")

def create(request: schemas.ShopRequest, db: Session):
    try:
        new_shop = models.GPSMaster(
            shop_code=request.shop_code, 
            location=request.location,
            address=request.address, 
            brand=request.brand,
            district=request.district, 
            latitude=request.latitude,
            longitude=request.longitude,
            matrix_status='to_create'
            )
        db.add(new_shop)
        db.commit()
        db.refresh(new_shop)
        return new_shop
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f'shop with {request.dict()} not created: {e}')
    
def delete(id: int, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == id)
        
        if not shop.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"shop with id {id} not found")
        
        shop.delete(synchronize_session=False)
        db.commit()
        return {f"shop with id {id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unable to delete shop {id}, error: {e}")

def update(id: int, request: schemas.ShopRequest, db: Session):
    try:
        shop = db.query(models.GPSMaster).filter(models.GPSMaster.id == id)
        if not shop.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"shop with id {id} not found")

        gps_changed = (
        shop.first().latitude != request.latitude or 
        shop.first().longitude != request.longitude
        )
        current_status = shop.first().matrix_status
        
        if gps_changed:
            shop.update({
                models.GPSMaster.shop_code : request.shop_code,
                models.GPSMaster.location : request.location,
                models.GPSMaster.address : request.address,
                models.GPSMaster.brand : request.brand,
                models.GPSMaster.district : request.district,
                models.GPSMaster.latitude : request.latitude,
                models.GPSMaster.longitude : request.longitude,
                models.GPSMaster.matrix_status : 'to_update'
            })
        else:
            shop.update({
                models.GPSMaster.shop_code : request.shop_code,
                models.GPSMaster.location : request.location,
                models.GPSMaster.address : request.address,
                models.GPSMaster.brand : request.brand,
                models.GPSMaster.district : request.district,
                models.GPSMaster.latitude : request.latitude,
                models.GPSMaster.longitude : request.longitude,
                models.GPSMaster.matrix_status : current_status
            })
        db.commit()
        return shop.first()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail= f"unable to update shop id {id}, error: {e}")
    
    
def shop_coords(shop: models.GPSMaster) -> dict:
    """Return only the fields the API needs."""
    return {
        "shop_code": shop.shop_code,
        "latitude":  shop.latitude,
        "longitude": shop.longitude,
    }