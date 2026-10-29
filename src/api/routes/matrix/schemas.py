from typing import List, Optional

from pydantic import BaseModel, Field


class MatrixSyncRequest(BaseModel):
    max_workers: Optional[int] = Field(
        default=10,
        ge=1,
        le=32,
        description="Parallel OSRM worker threads for matrix calculation",
    )


class MatrixSyncResponse(BaseModel):
    message: str
    pending_before: int


class MatrixStatsResponse(BaseModel):
    total_shops_in_matrix: int
    pending_updates: int
    total_distances_stored: int
    expected_distances: int
    matrix_completeness: str


class PendingShopItem(BaseModel):
    id: int
    shop_code: str
    location: Optional[str] = None
    brand: Optional[str] = None
    matrix_status: Optional[str] = None


class PendingShopsResponse(BaseModel):
    count: int
    shops: List[PendingShopItem]
