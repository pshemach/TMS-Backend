from fastapi import APIRouter, status,HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from src.database.services import shops_curd
from .. import schemas
from src.database import database


get_db = database.get_db

router = APIRouter(
    prefix='/master',
    tags=['master']
)

@router.get('/shop', status_code=status.HTTP_200_OK, response_model=List[schemas.ShopResponse])
def get_all_shop(db: Session = Depends(get_db)):
    try:
        shops = shops_curd.get_all(db)
        return shops
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/shop/{id}', status_code=status.HTTP_200_OK, response_model=schemas.ShopResponse)
def get_shop(id: int, db: Session = Depends(get_db)):
    try:
        shop = shops_curd.get_shop(id, db)
        if not shop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Shop with id {id} not found")
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/shop/shop_code/{shop_code}', status_code=status.HTTP_200_OK, response_model=schemas.ShopResponse)
def get_shop_by_code(shop_code: str, db: Session = Depends(get_db)):
    try:
        shop = shops_curd.get_shop_code(shop_code, db)
        if not shop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Shop with code {shop_code} not found")
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/shop', status_code=status.HTTP_201_CREATED, response_model=schemas.ShopResponse)
def create_shop(request: schemas.ShopRequest, db: Session = Depends(get_db)):
    try:
        new_shop = shops_curd.create(request, db)
        return new_shop
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete('/shop/{id}', status_code=status.HTTP_200_OK)
def delete_shop(id: int, db: Session = Depends(get_db)):
    try:
        msg = shops_curd.delete(id, db)
        if not msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Shop with id {id} not found")
        return msg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put('/shop/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=schemas.ShopResponse)
def update_shop(id: int, request: schemas.ShopRequest, db: Session = Depends(get_db)):
    try:
        shop = shops_curd.update(id, request, db)
        if not shop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Shop with id {id} not found")
        return shop
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))