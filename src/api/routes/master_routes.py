from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from src.api.database.repository import gps_master
from ..schemas import ShopRequest
from ..database import database


get_db = database.get_db

master_router = APIRouter(
    prefix='/master',
    tags=['master']
)


@master_router.post('/add_shop', status_code=status.HTTP_201_CREATED)
def create_shop(request: ShopRequest, db: Session = Depends(get_db)):
    new_shop = gps_master.create(request, db)
    return new_shop

@master_router.get('/get_shop')
def get_shop(db: Session = Depends(get_db)):
    shops = gps_master.get_all(db)
    return shops



