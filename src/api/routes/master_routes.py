from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from src.database.repository import gps_curd
from ..schemas import ShopRequest
from src.database import database


get_db = database.get_db

master_router = APIRouter(
    prefix='/master',
    tags=['master']
)

@master_router.get('/shop', status_code=status.HTTP_200_OK)
def get_all_shop(db: Session = Depends(get_db)):
    shops = gps_curd.get_all(db)
    return shops

@master_router.get('/shop/{id}', status_code=status.HTTP_200_OK)
def get_shop(id: int, db: Session = Depends(get_db)):
    shop = gps_curd.get_shop(id, db)
    return shop

@master_router.post('/shop', status_code=status.HTTP_201_CREATED)
def create_shop(request: ShopRequest, db: Session = Depends(get_db)):
    new_shop = gps_curd.create(request, db)
    return new_shop

@master_router.delete('/shop/{id}', status_code=status.HTTP_200_OK)
def delete_shop(id: int, db: Session = Depends(get_db)):
    msg = gps_curd.delete(id, db)
    return msg

@master_router.put('/shop/{id}', status_code=status.HTTP_202_ACCEPTED)
def update_shop(id: int, request: ShopRequest, db: Session = Depends(get_db)):
    msg = gps_curd.update(id, request, db)
    return msg