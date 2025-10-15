from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from ..schemas import ShopRequest
from ..database import database
from ..database import models

get_db = database.get_db

master_router = APIRouter(
    prefix='/master',
    tags=['master']
)


@master_router.post('/add_shop', status_code=status.HTTP_201_CREATED)
def create_shop(request: ShopRequest, db: Session = Depends(get_db)):
    new_shop = models.MasterGPS(shop_code=request.shop_code, location=request.location,
                                address=request.address, brand=request.brand,
                                district=request.district, latitude=request.latitude,
                                longitude=request.longitude)
    db.add(new_shop)
    db.commit()
    db.refresh(new_shop)
    return new_shop

@master_router.get('/get_shop')
def get_shop(db: Session = Depends(get_db)):
    shops = db.query(models.MasterGPS).all()
    return shops



