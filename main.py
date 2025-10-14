from fastapi import FastAPI
from src.api.routes import master_routes


app = FastAPI()


app.include_router(master_routes.master_router)