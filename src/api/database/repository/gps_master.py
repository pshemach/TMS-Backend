from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.api.database import models
from src.api import schemas


def get_all(db: Session):
    shops = db.query(models.GPSMaster).all()
    return shops

def create(request: schemas.ShopRequest, db: Session):
    try:
        new_shop = models.GPSMaster(shop_code=request.shop_code, location=request.location,
                                    address=request.address, brand=request.brand,
                                    district=request.district, latitude=request.latitude,
                                    longitude=request.longitude)
        db.add(new_shop)
        db.commit()
        db.refresh(new_shop)
        return new_shop
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f'shop not created (error): {e}')