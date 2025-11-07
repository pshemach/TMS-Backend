from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from typing import List
from src.database.repository import shops_curd
from .. import schemas
from src.database import database


get_db = database.get_db

master_router = APIRouter(
    prefix='/master',
    tags=['master']
)

@master_router.get('/shop', status_code=status.HTTP_200_OK, response_model=List[schemas.ShopResponse])
def get_all_shop(db: Session = Depends(get_db)):
    shops = shops_curd.get_all(db)
    return shops

@master_router.get('/shop/{id}', status_code=status.HTTP_200_OK, response_model=schemas.ShopResponse)
def get_shop(id: int, db: Session = Depends(get_db)):
    shop = shops_curd.get_shop(id, db)
    return shop

@master_router.get('/shop/shop_code/{shop_code}', status_code=status.HTTP_200_OK, response_model=schemas.ShopResponse)
def get_shop(shop_code: str, db: Session = Depends(get_db)):
    shop = shops_curd.get_shop_code(shop_code, db)
    return shop

@master_router.post('/shop', status_code=status.HTTP_201_CREATED)
def create_shop(request: schemas.ShopRequest, db: Session = Depends(get_db)):
    new_shop = shops_curd.create(request, db)
    return new_shop

@master_router.delete('/shop/{id}', status_code=status.HTTP_200_OK)
def delete_shop(id: int, db: Session = Depends(get_db)):
    msg = shops_curd.delete(id, db)
    return msg

@master_router.put('/shop/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.ShopResponse)
def update_shop(id: int, request: schemas.ShopRequest, db: Session = Depends(get_db)):
    shop = shops_curd.update(id, request, db)
    return shop