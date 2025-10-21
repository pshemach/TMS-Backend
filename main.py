from fastapi import FastAPI
from src.api.routes import master_routes, fleet_route
from src.database import models
from src.database.database import engine


app = FastAPI()

models.Base.metadata.create_all(bind=engine)

app.include_router(master_routes.master_router)
app.include_router(fleet_route.fleet_router)