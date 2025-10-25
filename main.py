from fastapi import FastAPI
from src.api.routes import fleet_routes, master_routes, vehicle_routes, vehicle_constrain_routes, geo_constraint_routes, predefined_route_routes
from src.database import models
from src.database.database import engine


app = FastAPI()

models.Base.metadata.create_all(bind=engine)

app.include_router(master_routes.master_router)
app.include_router(fleet_routes.fleet_router)
app.include_router(vehicle_routes.vehicle_router)
app.include_router(vehicle_constrain_routes.vehicle_constraint_router)
app.include_router(geo_constraint_routes.geo_constraint_router)
app.include_router(predefined_route_routes.router)
