from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.customers import repository, schemas

router = APIRouter(prefix="/location", tags=["location"])


@router.get("/customer", status_code=status.HTTP_200_OK, response_model=List[schemas.CustomerResponse])
def list_customers(db: Session = Depends(get_db)):
    try:
        return repository.get_all(db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/customer/code/{shop_code}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.CustomerResponse,
)
def get_customer_by_code(shop_code: str, db: Session = Depends(get_db)):
    try:
        customer = repository.get_shop_code(shop_code, db)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with code {shop_code} not found",
            )
        return customer
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/customer/{id}", status_code=status.HTTP_200_OK, response_model=schemas.CustomerResponse)
def get_customer(id: int, db: Session = Depends(get_db)):
    try:
        customer = repository.get_shop(id, db)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with id {id} not found",
            )
        return customer
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/customer", status_code=status.HTTP_201_CREATED, response_model=schemas.CustomerResponse)
def create_customer(request: schemas.CustomerRequest, db: Session = Depends(get_db)):
    try:
        return repository.create(request, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/customer/{id}", status_code=status.HTTP_200_OK)
def delete_customer(id: int, db: Session = Depends(get_db)):
    try:
        msg = repository.delete(id, db)
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with id {id} not found",
            )
        return msg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/customer/{id}", status_code=status.HTTP_202_ACCEPTED, response_model=schemas.CustomerResponse)
def update_customer(id: int, request: schemas.CustomerRequest, db: Session = Depends(get_db)):
    try:
        customer = repository.update(id, request, db)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with id {id} not found",
            )
        return customer
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
