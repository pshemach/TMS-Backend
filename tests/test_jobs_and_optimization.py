"""Job lifecycle and the validation gate in front of the solver.

Optimization tests replace the solver callback. They check that a job is
accepted and stored; they do not call OSRM or OR-Tools.
"""

from datetime import date

from src.infrastructure.database import models
from tests.factories import create_depot, create_fleet, create_order, create_shop, create_vehicle, seed_job


def _silence_solver(monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.optimization.endpoints.run_optimization_task",
        lambda *args, **kwargs: None,
    )


def test_optimize_rejects_an_empty_plan(client):
    no_vehicles = client.post(
        "/optimize/",
        json={"day": "2026-10-29", "vehicles": [], "selected_orders": [1]},
    )
    no_orders = client.post(
        "/optimize/",
        json={"day": "2026-10-29", "vehicles": [{"vehicle_id": 1}], "selected_orders": []},
    )
    assert no_vehicles.status_code == 400
    assert "vehicle" in no_vehicles.json()["detail"].lower()
    assert no_orders.status_code == 400
    assert "order" in no_orders.json()["detail"].lower()
    assert client.get("/job/").json() == []


def test_optimize_rejects_completed_orders_and_unknown_vehicles(client, monkeypatch):
    _silence_solver(monkeypatch)
    shop = create_shop(client)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])
    completed = create_order(client, shop["id"])
    client.put(f"/order/{completed['id']}", json={"status": "completed"})

    only_completed = client.post(
        "/optimize/",
        json={
            "day": "2026-10-29",
            "vehicles": [{"vehicle_id": vehicle["id"]}],
            "selected_orders": [completed["id"]],
        },
    )
    assert only_completed.status_code == 400
    assert "uncompleted" in only_completed.json()["detail"]

    pending = create_order(client, shop["id"])
    unknown_vehicle = client.post(
        "/optimize/",
        json={
            "day": "2026-10-29",
            "vehicles": [{"vehicle_id": 99999}],
            "selected_orders": [pending["id"]],
        },
    )
    assert unknown_vehicle.status_code == 400
    repeated_vehicle = client.post(
        "/optimize/",
        json={
            "day": "2026-10-29",
            "vehicles": [{"vehicle_id": vehicle["id"]}, {"vehicle_id": vehicle["id"]}],
            "selected_orders": [pending["id"]],
        },
    )
    assert repeated_vehicle.status_code == 400
    assert client.get("/job/").json() == []


def test_optimize_opens_a_running_job_and_hands_it_to_the_solver(client, monkeypatch):
    seen = {}

    def capture(db, request, job_id):
        seen["job_id"] = job_id
        seen["orders"] = list(request.selected_orders)

    monkeypatch.setattr("src.api.routes.optimization.endpoints.run_optimization_task", capture)

    shop = create_shop(client)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])
    order = create_order(client, shop["id"])

    started = client.post(
        "/optimize/",
        json={
            "day": "2026-10-29",
            "vehicles": [{"vehicle_id": vehicle["id"], "predefined_route_id": None}],
            "selected_orders": [order["id"]],
            "use_time_windows": False,
        },
    )
    assert started.status_code == 200
    body = started.json()
    assert body["message"] == "Optimization started"
    assert seen["job_id"] == body["job_id"]
    assert seen["orders"] == [order["id"]]

    job = client.get(f"/job/{body['job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "running"
    assert job.json()["name"] == "Delivery 2026-10-29"
    assert job.json()["day"] == "2026-10-29"
    assert job.json()["total_routes"] == 0


def test_job_summary_filters_by_day(client, db_session):
    shop = create_shop(client)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])
    october = seed_job(
        db_session,
        vehicle_id=vehicle["id"],
        day=date(2026, 10, 29),
        stops=[{"location_id": shop["id"], "order_id": None}],
    )
    seed_job(
        db_session,
        vehicle_id=vehicle["id"],
        day=date(2026, 11, 2),
        stops=[{"location_id": shop["id"], "order_id": None}],
    )

    window = client.get("/job/", params={"date_from": "2026-10-01", "date_to": "2026-10-31"})
    assert window.status_code == 200
    assert [row["id"] for row in window.json()] == [october.id]
    assert window.json()[0]["route_count"] == 1


def test_route_views_hide_depot_stops_and_keep_visit_order(client, db_session):
    depot = create_depot(client)
    shop = create_shop(client, shop_code="DROP-1")
    later = create_shop(client, shop_code="DROP-2", latitude=7.29, longitude=80.63)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"], vehicle_name="LH-10")
    order = create_order(client, shop["id"], order_id="PO-STOP")
    job = seed_job(
        db_session,
        vehicle_id=vehicle["id"],
        stops=[
            {"location_id": depot["id"]},
            {"location_id": shop["id"], "order_id": "PO-STOP"},
            {"location_id": later["id"], "order_id": None},
        ],
    )

    summary = client.get(f"/job/{job.id}")
    assert summary.status_code == 200
    assert summary.json()["total_routes"] == 1
    assert summary.json()["total_stops"] == 2
    assert summary.json()["routes"][0]["stop_count"] == 2

    routes = client.get(f"/job/{job.id}/routes")
    assert routes.status_code == 200
    route = routes.json()[0]
    assert route["vehicle_name"] == "LH-10"
    assert route["total_distance"] == 42.5
    assert route["folium_html"] == "<div>map</div>"
    assert [stop["location_code"] for stop in route["stops"]] == ["DROP-1", "DROP-2"]
    assert route["stops"][0]["order_id"] == "PO-STOP"
    assert route["stops"][0]["location_coords"]["location_code"] == "DROP-1"

    visits = client.get(f"/job/vehicle/{vehicle['id']}/visits", params={"job_id": job.id})
    assert visits.status_code == 200
    assert [visit["location_code"] for visit in visits.json()] == ["DROP-1", "DROP-2"]

    one_route = client.get(f"/job/vehicle/{vehicle['id']}/route", params={"job_id": job.id})
    assert one_route.status_code == 200
    assert one_route.json()["id"] == route["id"]

    assert client.get(f"/order/{order['id']}").json()["status"] == "pending"


def test_completing_a_job_completes_its_orders_and_blocks_deletion(client, db_session):
    shop = create_shop(client)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])
    order = create_order(client, shop["id"], order_id="PO-FINISH")
    job = seed_job(
        db_session,
        vehicle_id=vehicle["id"],
        status=models.JobStatus.PLANNED,
        stops=[{"location_id": shop["id"], "order_id": "PO-FINISH"}],
    )

    completed = client.patch(f"/job/{job.id}/complete")
    assert completed.status_code == 200
    assert completed.json()["job_status"] == "completed"
    finished = client.get(f"/order/{order['id']}").json()
    assert finished["status"] == "completed"

    blocked = client.delete(f"/order/{order['id']}")
    assert blocked.status_code == 400


def test_cancelling_a_job_returns_orders_to_pending_and_marks_the_job_failed(client, db_session):
    shop = create_shop(client)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])
    order = create_order(client, shop["id"], order_id="PO-CANCEL")
    client.put(f"/order/{order['id']}", json={"status": "active"})
    db_session.commit()
    job = seed_job(
        db_session,
        vehicle_id=vehicle["id"],
        stops=[{"location_id": shop["id"], "order_id": "PO-CANCEL"}],
    )
    order_row = db_session.query(models.Order).filter(models.Order.id == order["id"]).one()
    order_row.job_id = job.id
    db_session.commit()

    cancelled = client.patch(f"/job/{job.id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["job_status"] == "failed"

    restored = client.get(f"/order/{order['id']}").json()
    assert restored["status"] == "pending"
    assert client.get(f"/job/{job.id}").json()["status"] == "failed"


def test_deleting_a_job_resets_linked_orders_and_removes_routes(client, db_session):
    shop = create_shop(client)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])
    order = create_order(client, shop["id"], order_id="PO-RESET")
    job = seed_job(
        db_session,
        vehicle_id=vehicle["id"],
        stops=[{"location_id": shop["id"], "order_id": "PO-RESET"}],
    )
    order_row = db_session.query(models.Order).filter(models.Order.id == order["id"]).one()
    order_row.job_id = job.id
    order_row.status = models.OrderStatus.ACTIVE
    db_session.commit()

    deleted = client.delete(f"/job/{job.id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "ok"
    assert "PO-RESET" in deleted.json()["reset_orders"]
    assert client.get(f"/job/{job.id}").status_code == 404
    assert client.get(f"/job/{job.id}/routes").status_code == 404
    assert client.get(f"/order/{order['id']}").json()["status"] == "pending"


def test_unknown_job_and_vehicle_route_return_404(client):
    assert client.get("/job/99999").status_code == 404
    assert client.get("/job/99999/routes").status_code == 404
    assert client.delete("/job/99999").status_code == 404
    assert client.patch("/job/99999/complete").status_code == 404
    assert client.patch("/job/99999/cancel").status_code == 404
    assert client.get("/job/vehicle/99999/visits").status_code == 404
    assert client.get("/job/vehicle/99999/route").status_code == 404
