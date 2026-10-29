"""Isolated API test harness.

The suite builds its own FastAPI app and SQLite database. It does not import
``src.api.app``, so collection never opens the database configured in ``.env``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.deps import get_db
from src.api.routes.depots.endpoints import router as depots_router
from src.api.routes.fleets.endpoints import router as fleets_router
from src.api.routes.geo_constraints.endpoints import router as geo_constraints_router
from src.api.routes.jobs.endpoints import router as jobs_router
from src.api.routes.optimization.endpoints import router as optimization_router
from src.api.routes.order_groups.endpoints import router as order_groups_router
from src.api.routes.orders.endpoints import router as orders_router
from src.api.routes.predefined_routes.endpoints import router as predefined_routes_router
from src.api.routes.shops.endpoints import router as shops_router
from src.api.routes.vehicle_constraints.endpoints import router as vehicle_constraints_router
from src.api.routes.vehicles.endpoints import router as vehicles_router
from src.infrastructure.database.base import Base
from src.infrastructure.database import models  # noqa: F401  (register tables)


@compiles(LONGTEXT, "sqlite")
def _compile_mysql_longtext_as_text(element, compiler, **kwargs):
    """``job_routes.folium_html`` is MySQL LONGTEXT. SQLite has no such type."""
    return "TEXT"


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _build_app() -> FastAPI:
    application = FastAPI()
    for resource_router in (
        shops_router,
        depots_router,
        fleets_router,
        vehicles_router,
        vehicle_constraints_router,
        geo_constraints_router,
        predefined_routes_router,
        orders_router,
        order_groups_router,
        optimization_router,
        jobs_router,
    ):
        application.include_router(resource_router)
    return application


app = _build_app()


@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
