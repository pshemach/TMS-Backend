"""Geo constraints and predefined routes used as solver inputs."""

from tests.factories import create_fleet, create_shop, create_vehicle


def test_geo_constraint_requires_two_different_known_shops(client):
    start = create_shop(client, shop_code="START")
    end = create_shop(client, shop_code="END", latitude=7.2906, longitude=80.6337)

    same_shop = client.post(
        "/geo-constraint/",
        json={"start_shop_id": start["id"], "end_shop_id": start["id"]},
    )
    assert same_shop.status_code == 400

    missing = client.post(
        "/geo-constraint/",
        json={"start_shop_id": start["id"], "end_shop_id": 99999},
    )
    assert missing.status_code == 404

    created = client.post(
        "/geo-constraint/",
        json={"start_shop_id": start["id"], "end_shop_id": end["id"]},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["vehicle"] is None
    assert body["start_shop"]["shop_code"] == "START"
    assert body["end_shop"]["shop_code"] == "END"

    duplicate = client.post(
        "/geo-constraint/",
        json={"start_shop_id": start["id"], "end_shop_id": end["id"]},
    )
    assert duplicate.status_code == 400
    assert len(client.get("/geo-constraint/").json()) == 1


def test_geo_constraint_can_be_assigned_to_one_vehicle(client):
    start = create_shop(client)
    end = create_shop(client, latitude=7.2, longitude=80.1)
    fleet = create_fleet(client)
    vehicle = create_vehicle(client, fleet["id"], vehicle_name="Route Truck")
    other = create_vehicle(client, fleet["id"], vehicle_name="Other Truck")

    created = client.post(
        "/geo-constraint/",
        json={
            "start_shop_id": start["id"],
            "end_shop_id": end["id"],
            "vehicle_id": vehicle["id"],
        },
    )
    assert created.status_code == 201
    assert created.json()["vehicle"]["id"] == vehicle["id"]
    assert created.json()["vehicle"]["vehicle_name"] == "Route Truck"

    again = client.post(
        "/geo-constraint/",
        json={
            "start_shop_id": start["id"],
            "end_shop_id": end["id"],
            "vehicle_id": vehicle["id"],
        },
    )
    assert again.status_code == 400

    by_vehicle = client.get(f"/geo-constraint/by-vehicle/{vehicle['id']}")
    assert by_vehicle.status_code == 200
    assert len(by_vehicle.json()) == 1

    filtered = client.get("/geo-constraint/", params={"fleet_id": fleet["id"]})
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    missing_vehicle = client.post(
        "/geo-constraint/",
        json={"start_shop_id": end["id"], "end_shop_id": start["id"], "vehicle_id": 99999},
    )
    assert missing_vehicle.status_code == 404

    # Omitting vehicle_id is treated as an explicit clear.
    cleared = client.put(
        f"/geo-constraint/{created.json()['id']}",
        json={"end_shop_id": end["id"]},
    )
    assert cleared.status_code == 200
    assert cleared.json()["vehicle"] is None

    reassigned = client.put(
        f"/geo-constraint/{created.json()['id']}",
        json={"vehicle_id": other["id"]},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["vehicle"]["id"] == other["id"]


def test_unknown_geo_constraint_returns_404(client):
    assert client.get("/geo-constraint/99999").status_code == 404
    assert client.delete("/geo-constraint/99999").status_code == 404
    assert client.put("/geo-constraint/99999", json={"vehicle_id": 1}).status_code == 404


def test_predefined_route_keeps_shop_order_and_rejects_unknown_shops(client):
    first = create_shop(client, shop_code="A")
    second = create_shop(client, shop_code="B", latitude=7.29, longitude=80.63)
    third = create_shop(client, shop_code="C", latitude=6.05, longitude=80.22)

    missing = client.post(
        "/predefined-route/",
        json={"name": "Coast", "shops": [{"shop_id": first["id"]}, {"shop_id": 99999}]},
    )
    assert missing.status_code == 404

    created = client.post(
        "/predefined-route/",
        json={
            "name": "Coast",
            "shops": [
                {"shop_id": first["id"]},
                {"shop_id": second["id"]},
                {"shop_id": third["id"]},
            ],
        },
    )
    assert created.status_code == 201
    codes = [stop["shop"]["shop_code"] for stop in created.json()["shops"]]
    assert codes == ["A", "B", "C"]

    duplicate = client.post(
        "/predefined-route/",
        json={"name": "Coast", "shops": [{"shop_id": first["id"]}]},
    )
    assert duplicate.status_code == 400

    renamed = client.put(
        f"/predefined-route/{created.json()['id']}",
        json={"name": "Hill", "shops": [{"shop_id": third["id"]}, {"shop_id": first["id"]}]},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Hill"
    assert [stop["shop"]["shop_code"] for stop in renamed.json()["shops"]] == ["C", "A"]

    fetched = client.get(f"/predefined-route/{created.json()['id']}")
    assert fetched.status_code == 200
    assert client.get("/predefined-route/").json()[0]["name"] == "Hill"

    deleted = client.delete(f"/predefined-route/{created.json()['id']}")
    assert deleted.status_code == 200
    assert client.get("/predefined-route/").json() == []


def test_unknown_predefined_route_returns_404(client):
    assert client.get("/predefined-route/99999").status_code == 404
    assert client.delete("/predefined-route/99999").status_code == 404
    assert client.put("/predefined-route/99999", json={"name": "Missing"}).status_code == 404
