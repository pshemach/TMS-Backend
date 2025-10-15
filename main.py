from fastapi import FastAPI
from src.api.routes import master_routes
from src.api.database import models
from src.api.database.database import engine


app = FastAPI()

models.Base.metadata.create_all(bind=engine)

app.include_router(master_routes.master_router)