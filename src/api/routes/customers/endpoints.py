from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes.customers import repository, schemas

router = APIRouter(prefix="/location", tags=["location"])


def _to_response(row) -> schemas.CustomerResponse:
    return schemas.CustomerResponse(
        id=row.id,
        location_code=row.location_code,
        location_name=row.location_name,
        address=row.address,
        brand=row.brand or "",
        district=row.district or "",
        latitude=row.latitude,
        longitude=row.longitude,
        location_type=row.location_type.value if hasattr(row.location_type, "value") else str(row.location_type),
        matrix_status=row.matrix_status.value if hasattr(row.matrix_status, "value") else str(row.matrix_status),
    )


@router.get("/customer", status_code=status.HTTP_200_OK, response_model=List[schemas.CustomerResponse])
def list_customers(db: Session = Depends(get_db)):
    try:
        return [_to_response(r) for r in repository.get_all(db)]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/customer/code/{location_code}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.CustomerResponse,
)
def get_customer_by_code(location_code: str, db: Session = Depends(get_db)):
    try:
        customer = repository.get_by_code(location_code, db)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with code {location_code} not found",
            )
        return _to_response(customer)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/customer/{id}", status_code=status.HTTP_200_OK, response_model=schemas.CustomerResponse)
def get_customer(id: int, db: Session = Depends(get_db)):
    try:
        customer = repository.get_by_id(id, db)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with id {id} not found",
            )
        return _to_response(customer)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/customer", status_code=status.HTTP_201_CREATED, response_model=schemas.CustomerResponse)
def create_customer(request: schemas.CustomerRequest, db: Session = Depends(get_db)):
    try:
        return _to_response(repository.create(request, db))
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
        return _to_response(customer)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
