from fastapi import APIRouter, status
from ..schemas import ShopRequest

master_router = APIRouter(
    prefix='/master',
    tags=['master']
)


@master_router.post('/add_shop', status_code=status.HTTP_201_CREATED)
def create_shop(request: ShopRequest):
    print(request)
    return request




