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
    total_locations_in_matrix: int
    pending_updates: int
    total_distances_stored: int
    expected_distances: int
    matrix_completeness: str


class PendingLocationItem(BaseModel):
    id: int
    shop_code: str
    location: Optional[str] = None
    brand: Optional[str] = None
    matrix_status: Optional[str] = None


class PendingLocationsResponse(BaseModel):
    count: int
    locations: List[PendingLocationItem]
