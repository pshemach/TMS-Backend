"""Fleet membership and the vehicle counts that routing depends on."""

from tests.factories import (
    constraint_payload,
    create_fleet,
    create_vehicle,
    fleet_payload,
    vehicle_payload,
)


def test_fleet_catalogue_is_404_until_the_first_fleet_exists(client):
    response = client.get("/fleet/")
    assert response.status_code == 404
    assert "No fleets" in response.json()["detail"]


def test_new_fleet_starts_with_zero_vehicles_regardless_of_client_counts(client):
    created = create_fleet(client)
    assert created["total_vehicles"] == 0
    assert created["available_vehicles"] == 0
    assert created["vehicles"] == []
    assert created["status"] == "active"


def test_fleet_status_must_be_active_or_inactive(client):
    response = client.post("/fleet/", json=fleet_payload(status="paused"))
    assert response.status_code == 422


def test_unknown_fleet_returns_404(client):
    assert client.get("/fleet/99999").status_code == 404
    assert client.delete("/fleet/99999").status_code == 404
    assert client.put("/fleet/99999", json=fleet_payload()).status_code == 404


def test_fleet_rename_does_not_reset_vehicle_counts(client):
    fleet = create_fleet(client, fleet_name="Original")
    create_vehicle(client, fleet["id"], status="available")

    renamed = client.put(
        f"/fleet/{fleet['id']}",
        json=fleet_payload(fleet_name="Renamed", status="inactive"),
    )
    assert renamed.status_code == 202
    body = renamed.json()
    assert body["fleet_name"] == "Renamed"
    assert body["status"] == "inactive"
    assert body["total_vehicles"] == 1
    assert body["available_vehicles"] == 1
    assert body["vehicles"][0]["constraint"]["fleet"] == "Original"


def test_vehicle_counts_follow_availability(client):
    fleet = create_fleet(client)
    available = create_vehicle(client, fleet["id"], status="available", vehicle_name="Ready")
    maintenance = create_vehicle(
        client, fleet["id"], status="maintenance", vehicle_name="Workshop"
    )

    listed = client.get(f"/fleet/{fleet['id']}")
    assert listed.status_code == 200
    assert listed.json()["total_vehicles"] == 2
    assert listed.json()["available_vehicles"] == 1

    parked = client.put(
        f"/vehicle/{available['id']}",
        json=vehicle_payload(vehicle_name="Ready", status="unavailable"),
    )
    assert parked.status_code == 202
    after_park = client.get(f"/fleet/{fleet['id']}").json()
    assert after_park["available_vehicles"] == 0
    assert after_park["total_vehicles"] == 2

    released = client.put(
        f"/vehicle/{maintenance['id']}",
        json=vehicle_payload(vehicle_name="Workshop", status="available"),
    )
    assert released.status_code == 202
    after_release = client.get(f"/fleet/{fleet['id']}").json()
    assert after_release["available_vehicles"] == 1

    removed = client.delete(f"/vehicle/{maintenance['id']}")
    assert removed.status_code == 200
    assert "deleted" in removed.json()["detail"]
    remaining = client.get(f"/fleet/{fleet['id']}").json()
    assert remaining["total_vehicles"] == 1
    assert remaining["available_vehicles"] == 0
    assert client.get(f"/vehicle/{maintenance['id']}").status_code == 404


def test_vehicle_is_created_with_default_constraint(client):
    fleet = create_fleet(client, fleet_name="Southern")
    vehicle = create_vehicle(client, fleet["id"], vehicle_name="LH-2214", status="available")

    constraint = vehicle["constraint"]
    assert constraint["vehicle_id"] == vehicle["id"]
    assert constraint["vehicle_name"] == "LH-2214"
    assert constraint["fleet"] == "Southern"
    assert constraint["payload"] == 10000.0
    assert constraint["volume"] == 40.0
    assert constraint["max_distance"] == 1200.0
    assert constraint["max_visits"] == 15
    assert constraint["time_window"] == "00:00-23:59"
    assert constraint["days"] == 1


def test_vehicle_status_must_be_a_known_value(client):
    fleet = create_fleet(client)
    response = client.post(
        f"/vehicle/{fleet['id']}",
        json=vehicle_payload(status="broken"),
    )
    assert response.status_code == 422
    assert client.get(f"/fleet/{fleet['id']}").json()["total_vehicles"] == 0


def test_vehicle_cannot_be_added_to_a_missing_fleet(client):
    response = client.post("/vehicle/99999", json=vehicle_payload())
    assert response.status_code == 404


def test_vehicle_list_can_be_filtered_by_fleet(client):
    western = create_fleet(client, fleet_name="Western")
    southern = create_fleet(client, fleet_name="Southern")
    create_vehicle(client, western["id"], vehicle_name="West-1")
    create_vehicle(client, southern["id"], vehicle_name="South-1")

    western_only = client.get("/vehicle/", params={"fleet_id": western["id"]})
    assert western_only.status_code == 200
    names = [row["vehicle_name"] for row in western_only.json()]
    assert names == ["West-1"]

    missing_fleet = client.get("/vehicle/", params={"fleet_id": 99999})
    assert missing_fleet.status_code == 404


def test_vehicle_catalogue_is_404_when_empty(client):
    response = client.get("/vehicle/")
    assert response.status_code == 404


def test_unknown_vehicle_returns_404(client):
    assert client.get("/vehicle/99999").status_code == 404
    assert client.delete("/vehicle/99999").status_code == 404
    assert client.put("/vehicle/99999", json=vehicle_payload()).status_code == 404


def test_deleting_a_fleet_removes_its_vehicles(client):
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])

    deleted = client.delete(f"/fleet/{fleet['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/vehicle/{vehicle['id']}").status_code == 404
    assert client.get("/fleet/").status_code == 404


def test_constraint_update_replaces_capacity_limits(client):
    fleet = create_fleet(client, fleet_name="Central")
    vehicle = create_vehicle(client, fleet["id"], vehicle_name="CTB-9", type="lorry")

    updated = client.put(
        f"/vehicle-constraint/{vehicle['id']}",
        json=constraint_payload(days=3),
    )
    assert updated.status_code == 202
    body = updated.json()
    assert body["payload"] == 8000.0
    assert body["volume"] == 30.0
    assert body["max_distance"] == 400.0
    assert body["max_visits"] == 8
    assert body["time_window"] == "06:00-18:00"
    assert body["vehicle_name"] == "CTB-9"
    assert body["fleet"] == "Central"
    assert body["type"] == "lorry"
    # The request accepts ``days``, but the repository never assigns it.
    assert body["days"] == 1

    reread = client.get(f"/vehicle/{vehicle['id']}")
    assert reread.json()["constraint"]["payload"] == 8000.0


def test_constraint_capacity_must_be_positive(client):
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"])

    zero_payload = client.put(
        f"/vehicle-constraint/{vehicle['id']}",
        json=constraint_payload(payload=0),
    )
    negative_volume = client.put(
        f"/vehicle-constraint/{vehicle['id']}",
        json=constraint_payload(volume=-1),
    )
    assert zero_payload.status_code == 422
    assert negative_volume.status_code == 422
    assert client.get(f"/vehicle/{vehicle['id']}").json()["constraint"]["payload"] == 10000.0


def test_constraint_for_unknown_vehicle_is_404(client):
    response = client.put("/vehicle-constraint/99999", json=constraint_payload())
    assert response.status_code == 404
