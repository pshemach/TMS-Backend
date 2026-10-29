"""Request builders and arrange-helpers for API tests.

Coordinates stay inside the Sri Lanka bounds enforced by the shop and depot
schemas (latitude 5.5–10.5, longitude 78.5–82.5).
"""

from __future__ import annotations

import itertools
from datetime import date

from src.infrastructure.database import models

_ids = itertools.count(1)


def _next(prefix: str) -> str:
    return f"{prefix}{next(_ids):04d}"


def shop_payload(**overrides) -> dict:
    payload = {
        "shop_code": _next("SH"),
        "location": "Colombo 03",
        "address": "12 Galle Road",
        "brand": "keells",
        "district": "Colombo",
        "latitude": 6.9271,
        "longitude": 79.8612,
    }
    payload.update(overrides)
    return payload


def depot_payload(**overrides) -> dict:
    payload = {
        "depot_code": _next("DP"),
        "location": "Orugodawatta",
        "address": "Baseline Road",
        "district": "Colombo",
        "latitude": 6.9480,
        "longitude": 79.8780,
    }
    payload.update(overrides)
    return payload


def fleet_payload(**overrides) -> dict:
    payload = {
        "fleet_name": _next("Western Fleet "),
        "type": "trucks",
        "region": "Western",
        "manager": "Nimal Perera",
        "status": "active",
    }
    payload.update(overrides)
    return payload


def vehicle_payload(**overrides) -> dict:
    payload = {
        "vehicle_name": _next("Truck "),
        "type": "truck",
        "status": "available",
        "location": "Colombo",
    }
    payload.update(overrides)
    return payload


def order_payload(shop_id: int, **overrides) -> dict:
    payload = {
        "order_id": _next("PO-"),
        "shop_id": shop_id,
        "po_value": 150000.0,
        "volume": 2.5,
        "po_date": "2026-10-29",
        "time_window": {"start": "09:00:00", "end": "17:00:00"},
        "priority": "high",
    }
    payload.update(overrides)
    return payload


def constraint_payload(**overrides) -> dict:
    payload = {
        "days": 1,
        "payload": 8000.0,
        "volume": 30.0,
        "time_window": "06:00-18:00",
        "max_distance": 400.0,
        "max_visits": 8,
    }
    payload.update(overrides)
    return payload


def create_shop(client, **overrides) -> dict:
    response = client.post("/master/shop", json=shop_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_depot(client, **overrides) -> dict:
    response = client.post("/master/depot", json=depot_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_fleet(client, **overrides) -> dict:
    response = client.post("/fleet/", json=fleet_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_vehicle(client, fleet_id: int, **overrides) -> dict:
    response = client.post(f"/vehicle/{fleet_id}", json=vehicle_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_order(client, shop_id: int, **overrides) -> dict:
    response = client.post("/order/", json=order_payload(shop_id, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def seed_job(db_session, *, vehicle_id: int, day: date | None = None, status=None, stops: list[dict]):
    """Insert a job, one route, and stops directly.

    The public API creates jobs only through optimization. Lifecycle tests
    arrange the route graph here, then exercise ``/job`` over HTTP.
    """
    job = models.Job(
        name="Manual delivery",
        day=day or date(2026, 10, 29),
        status=status or models.JobStatus.PLANNED,
    )
    db_session.add(job)
    db_session.flush()

    route = models.JobRoute(
        job_id=job.id,
        vehicle_id=vehicle_id,
        total_distance=42.5,
        total_time=95.0,
        folium_html="<div>map</div>",
    )
    db_session.add(route)
    db_session.flush()

    for index, stop in enumerate(stops, start=1):
        db_session.add(
            models.JobStop(
                route_id=route.id,
                shop_id=stop["shop_id"],
                sequence=index,
                order_id=stop.get("order_id"),
            )
        )
    db_session.commit()
    db_session.refresh(job)
    return job
