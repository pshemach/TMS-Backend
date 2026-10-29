"""Shops and depots share ``master_gps`` and are split by brand."""

import pytest

from tests.factories import create_depot, create_order, create_shop, depot_payload, shop_payload


def test_openapi_exposes_master_data_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/location/customer" in paths
    assert "/location/depot" in paths


def test_shop_list_is_empty_array_when_nothing_is_stored(client):
    response = client.get("/location/customer")
    assert response.status_code == 200
    assert response.json() == []


def test_shop_lifecycle_persists_coordinates_and_matrix_flag(client):
    created = create_shop(client, shop_code="KEE-COL-01", location="Bambalapitiya")

    assert created["location_code"] == "KEE-COL-01"
    assert created["matrix_status"] == "to_create"
    assert created["latitude"] == 6.9271

    fetched = client.get(f"/location/customer/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["location_name"] == "Bambalapitiya"

    by_code = client.get("/location/customer/code/KEE-COL-01")
    assert by_code.status_code == 200
    assert by_code.json()["id"] == created["id"]

    renamed = shop_payload(
        shop_code="KEE-COL-01",
        location="Bambalapitiya renamed",
        latitude=created["latitude"],
        longitude=created["longitude"],
    )
    updated = client.put(f"/location/customer/{created['id']}", json=renamed)
    assert updated.status_code == 202
    assert updated.json()["location_name"] == "Bambalapitiya renamed"
    assert updated.json()["matrix_status"] == "to_create"

    moved = shop_payload(
        shop_code="KEE-COL-01",
        location="Bambalapitiya renamed",
        latitude=7.2906,
        longitude=80.6337,
    )
    moved_response = client.put(f"/location/customer/{created['id']}", json=moved)
    assert moved_response.status_code == 202
    assert moved_response.json()["matrix_status"] == "to_update"

    deleted = client.delete(f"/location/customer/{created['id']}")
    assert deleted.status_code == 200
    assert "deleted" in deleted.json()["message"]
    assert client.get(f"/location/customer/{created['id']}").status_code == 404


def test_coordinate_bounds_are_enforced(client):
    below = client.post("/location/customer", json=shop_payload(latitude=5.49, longitude=79.86))
    above = client.post("/location/customer", json=shop_payload(latitude=6.9, longitude=82.51))
    assert below.status_code == 422
    assert above.status_code == 422

    edges = client.post("/location/customer", json=shop_payload(latitude=5.5, longitude=82.5))
    assert edges.status_code == 201


def test_missing_shop_fields_are_rejected(client):
    payload = shop_payload()
    del payload["location_code"]
    response = client.post("/location/customer", json=payload)
    assert response.status_code == 422


def test_unknown_shop_lookups_return_404(client):
    assert client.get("/location/customer/99999").status_code == 404
    assert client.get("/location/customer/code/DOES-NOT-EXIST").status_code == 404
    assert client.delete("/location/customer/99999").status_code == 404
    assert client.put("/location/customer/99999", json=shop_payload()).status_code == 404


def test_duplicate_shop_code_is_not_stored_twice(client):
    payload = shop_payload(shop_code="UNIQUE-SHOP")
    assert client.post("/location/customer", json=payload).status_code == 201

    duplicate = client.post("/location/customer", json=payload)
    assert duplicate.status_code >= 400
    listed = client.get("/location/customer")
    assert [shop["location_code"] for shop in listed.json()].count("UNIQUE-SHOP") == 1


def test_depots_are_hidden_from_the_shop_catalogue(client):
    shop = create_shop(client, brand="keells")
    depot = create_depot(client)

    shops = client.get("/location/customer").json()
    depots = client.get("/location/depot").json()

    assert [row["id"] for row in shops] == [shop["id"]]
    assert [row["id"] for row in depots] == [depot["id"]]
    assert client.get(f"/location/customer/{depot['id']}").status_code == 404


def test_depot_create_forces_depot_brand_and_matrix_flag(client):
    created = create_depot(client, depot_code="DEP-01")
    assert created["location_code"] == "DEP-01"
    assert created["matrix_status"] == "to_create"
    assert "brand" not in created

    unchanged = depot_payload(
        depot_code="DEP-01",
        location="Orugodawatta yard",
        latitude=created["latitude"],
        longitude=created["longitude"],
    )
    kept = client.put(f"/location/depot/{created['id']}", json=unchanged)
    assert kept.status_code == 202
    assert kept.json()["matrix_status"] == "to_create"

    moved = depot_payload(depot_code="DEP-01", latitude=6.05, longitude=80.22)
    relocated = client.put(f"/location/depot/{created['id']}", json=moved)
    assert relocated.status_code == 202
    assert relocated.json()["matrix_status"] == "to_update"
    assert relocated.json()["location_code"] == "DEP-01"


@pytest.mark.xfail(
    reason=(
        "Depot routes catch HTTPException inside a bare except and answer 500. "
        "The detail still names the missing depot, but clients cannot branch on 404."
    ),
    strict=False,
)
def test_unknown_depot_returns_404(client):
    assert client.get("/location/depot/99999").status_code == 404
    assert client.delete("/location/depot/99999").status_code == 404
    missing_update = client.put("/location/depot/99999", json=depot_payload())
    assert missing_update.status_code == 404


@pytest.mark.xfail(
    reason="GET /location/depot/{id} turns a shop id into HTTP 500 instead of 404.",
    strict=False,
)
def test_looking_up_a_shop_as_a_depot_returns_404(client):
    shop = create_shop(client)
    assert client.get(f"/location/depot/{shop['id']}").status_code == 404


def test_duplicate_depot_code_is_not_stored_twice(client):
    payload = depot_payload(depot_code="DEP-DUP")
    assert client.post("/location/depot", json=payload).status_code == 201
    duplicate = client.post("/location/depot", json=payload)
    assert duplicate.status_code >= 400
    codes = [row["location_code"] for row in client.get("/location/depot").json()]
    assert codes.count("DEP-DUP") == 1


def test_shop_referenced_by_an_order_cannot_be_removed(client):
    shop = create_shop(client)
    create_order(client, shop["id"])

    response = client.delete(f"/location/customer/{shop['id']}")
    assert response.status_code >= 400
    assert client.get(f"/location/customer/{shop['id']}").status_code == 200


def test_deleting_a_depot_does_not_remove_shops(client):
    shop = create_shop(client)
    depot = create_depot(client)

    deleted = client.delete(f"/location/depot/{depot['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/location/customer/{shop['id']}").status_code == 200
    assert client.get("/location/depot").json() == []
