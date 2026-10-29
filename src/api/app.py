"""FastAPI application — API routers + UI."""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api.routes.depots.endpoints import router as depots_router
from src.api.routes.fleets.endpoints import router as fleets_router
from src.api.routes.geo_constraints.endpoints import router as geo_constraints_router
from src.api.routes.jobs.endpoints import router as jobs_router
from src.api.routes.matrix.endpoints import router as matrix_router
from src.api.routes.optimization.endpoints import router as optimization_router
from src.api.routes.order_groups.endpoints import router as order_groups_router
from src.api.routes.orders.endpoints import router as orders_router
from src.api.routes.predefined_routes.endpoints import router as predefined_routes_router
from src.api.routes.customers.endpoints import router as customers_router
from src.api.routes.vehicle_constraints.endpoints import router as vehicle_constraints_router
from src.api.routes.vehicles.endpoints import router as vehicles_router
from src.infrastructure import config
from src.infrastructure.config import UI_DIR, ensure_directories, validate
from src.infrastructure.database import models
from src.infrastructure.database.session import engine
# Configure Loguru sinks (console + file) before request handling starts.
from src.infrastructure import logging as _logging  # noqa: F401

validate()
ensure_directories()

app = FastAPI(title="TMS Backend", description="Transport Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)

# --- API ---
app.include_router(customers_router)
app.include_router(depots_router)
app.include_router(fleets_router)
app.include_router(vehicles_router)
app.include_router(vehicle_constraints_router)
app.include_router(geo_constraints_router)
app.include_router(predefined_routes_router)
app.include_router(orders_router)
app.include_router(order_groups_router)
app.include_router(optimization_router)
app.include_router(jobs_router)
app.include_router(matrix_router)


@app.get("/runtime-config.js", include_in_schema=False)
def runtime_config_js():
    """Browser config from env. Empty API_PUBLIC_URL = same-origin."""
    return Response(
        content=f"window.__TMS_API_BASE__ = {json.dumps(config.API_PUBLIC_URL)};\n",
        media_type="application/javascript",
    )


@app.get("/", include_in_schema=False)
def ui_index():
    return FileResponse(UI_DIR / "index.html")


# UI assets at /static/* — isolated from API paths (/fleet, /order, …)
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")
