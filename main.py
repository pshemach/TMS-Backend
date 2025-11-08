from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import (fleet_routes, shop_routes,depot_routes,  vehicle_routes, 
                            vehicle_constrain_routes, geo_constraint_routes, 
                            predefined_route_routes, order_routes, 
                            order_group_routes,optimization_routes, job_routes )
from src.database import models
from src.database.database import engine

app = FastAPI(description=f"{'='*10} TMS BACKEND API {'='*10}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

models.Base.metadata.create_all(bind=engine)

app.include_router(shop_routes.router)
app.include_router(depot_routes.router)
app.include_router(fleet_routes.fleet_router)
app.include_router(vehicle_routes.vehicle_router)
app.include_router(vehicle_constrain_routes.vehicle_constraint_router)
app.include_router(geo_constraint_routes.geo_constraint_router)
app.include_router(predefined_route_routes.router)
app.include_router(order_routes.router)
app.include_router(order_group_routes.router)
app.include_router(optimization_routes.router)
app.include_router(job_routes.router)