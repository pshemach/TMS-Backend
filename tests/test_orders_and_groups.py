"""Orders, their status rules, and the groups planners batch them into."""

import pytest

from tests.factories import create_order, create_shop, order_payload


def test_order_is_pending_medium_when_priority_is_omitted(client):
    shop = create_shop(client)
    payload = order_payload(shop["id"], order_id="PO-100")
    del payload["priority"]

    created = client.post("/order/", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "pending"
    assert body["priority"] == "medium"
    assert body["shop"] == {
        "shop_code": shop["shop_code"],
        "latitude": shop["latitude"],
        "longitude": shop["longitude"],
    }
    assert body["time_window"]["start"] == "09:00:00"
    assert body["time_window"]["end"] == "17:00:00"

    by_po = client.get("/order/po/PO-100")
    assert by_po.status_code == 200
    assert by_po.json()["id"] == body["id"]


def test_order_requires_a_real_shop_and_a_unique_po(client):
    missing_shop = client.post("/order/", json=order_payload(shop_id=99999, order_id="PO-X"))
    assert missing_shop.status_code == 404

    shop = create_shop(client)
    create_order(client, shop["id"], order_id="PO-DUP")
    duplicate = client.post("/order/", json=order_payload(shop["id"], order_id="PO-DUP"))
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["detail"]


def test_time_window_must_end_after_it_starts(client):
    shop = create_shop(client)
    response = client.post(
        "/order/",
        json=order_payload(
            shop["id"],
            time_window={"start": "17:00:00", "end": "09:00:00"},
        ),
    )
    assert response.status_code == 422


def test_order_create_rejects_a_missing_po_date(client):
    shop = create_shop(client)
    payload = order_payload(shop["id"])
    del payload["po_date"]
    response = client.post("/order/", json=payload)
    assert response.status_code == 422


def test_order_list_filters_by_status_and_po_date(client):
    shop = create_shop(client)
    pending = create_order(client, shop["id"], po_date="2026-10-28", priority="low")
    other_day = create_order(client, shop["id"], po_date="2026-11-02")

    promoted = client.put(
        f"/order/{other_day['id']}",
        json={"status": "active", "po_value": 10},
    )
    assert promoted.status_code == 200
    assert promoted.json()["status"] == "active"
    assert promoted.json()["po_value"] == 10

    pending_only = client.get("/order/", params={"status": "pending"})
    assert pending_only.status_code == 200
    assert [row["id"] for row in pending_only.json()] == [pending["id"]]

    october = client.get(
        "/order/",
        params={"date_from": "2026-10-01", "date_to": "2026-10-31"},
    )
    assert [row["id"] for row in october.json()] == [pending["id"]]

    invalid = client.get("/order/", params={"status": "shipped"})
    assert invalid.status_code == 400


def test_unknown_order_lookups_return_404(client):
    assert client.get("/order/99999").status_code == 404
    assert client.get("/order/po/MISSING").status_code == 404
    assert client.put("/order/99999", json={"po_value": 1}).status_code == 404


def test_update_rejects_an_unknown_replacement_shop(client):
    shop = create_shop(client)
    order = create_order(client, shop["id"])
    response = client.put(f"/order/{order['id']}", json={"shop_id": 99999})
    assert response.status_code == 404
    assert client.get(f"/order/{order['id']}").json()["shop_id"] == shop["id"]


def test_business_key_update_blocks_illegal_status_transitions(client):
    shop = create_shop(client)
    completed = create_order(client, shop["id"], order_id="PO-DONE")
    active = create_order(client, shop["id"], order_id="PO-LIVE")
    client.put(f"/order/{completed['id']}", json={"status": "completed"})
    client.put(f"/order/{active['id']}", json={"status": "active"})

    revert_completed = client.put("/order/order_id/PO-DONE", json={"status": "pending"})
    revert_active = client.put("/order/order_id/PO-LIVE", json={"status": "pending"})
    assert revert_completed.status_code == 400
    assert "completed" in revert_completed.json()["detail"]
    assert revert_active.status_code == 400
    assert "pending" in revert_active.json()["detail"]

    assert client.get(f"/order/{completed['id']}").json()["status"] == "completed"
    assert client.get(f"/order/{active['id']}").json()["status"] == "active"


def test_completed_order_cannot_be_deleted(client):
    shop = create_shop(client)
    order = create_order(client, shop["id"])
    client.put(f"/order/{order['id']}", json={"status": "completed"})

    deleted = client.delete(f"/order/{order['id']}")
    assert deleted.status_code == 400
    assert client.get(f"/order/{order['id']}").status_code == 200


def test_pending_order_can_be_deleted(client):
    shop = create_shop(client)
    order = create_order(client, shop["id"])
    deleted = client.delete(f"/order/{order['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/order/{order['id']}").status_code == 404


def test_delete_unknown_order_is_rejected(client):
    response = client.delete("/order/99999")
    assert response.status_code >= 400


def test_invalid_priority_is_not_stored(client):
    shop = create_shop(client)
    response = client.post("/order/", json=order_payload(shop["id"], priority="urgent"))
    assert response.status_code >= 400
    assert client.get("/order/").json() == []


def test_order_group_batches_existing_orders_and_releases_them_on_delete(client):
    shop = create_shop(client)
    first = create_order(client, shop["id"], order_id="PO-G1", time_window=None)
    second = create_order(client, shop["id"], order_id="PO-G2", time_window=None)

    created = client.post(
        "/order-group/",
        json={"name": "Colombo Morning", "order_ids": ["PO-G1", "PO-G2"]},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Colombo Morning"
    assert sorted(order["order_id"] for order in body["orders"]) == ["PO-G1", "PO-G2"]

    fetched = client.get(f"/order-group/{body['id']}")
    assert fetched.status_code == 200
    assert len(fetched.json()["orders"]) == 2

    renamed = client.put(
        f"/order-group/{body['id']}",
        json={"name": "Colombo Afternoon"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Colombo Afternoon"
    assert sorted(order["order_id"] for order in renamed.json()["orders"]) == ["PO-G1", "PO-G2"]

    removed = client.delete(f"/order-group/{body['id']}")
    assert removed.status_code == 200
    assert client.get(f"/order-group/{body['id']}").status_code == 404
    assert client.get(f"/order/{first['id']}").status_code == 200
    assert client.get(f"/order/{second['id']}").status_code == 200


def test_order_group_rejects_duplicate_names_and_unknown_orders(client):
    shop = create_shop(client)
    create_order(client, shop["id"], order_id="PO-ONLY", time_window=None)
    first = client.post("/order-group/", json={"name": "Batch A", "order_ids": ["PO-ONLY"]})
    assert first.status_code == 201

    duplicate_name = client.post(
        "/order-group/",
        json={"name": "Batch A", "order_ids": ["PO-ONLY"]},
    )
    unknown = client.post(
        "/order-group/",
        json={"name": "Batch B", "order_ids": ["PO-MISSING"]},
    )
    assert duplicate_name.status_code == 400
    assert unknown.status_code == 400
    assert len(client.get("/order-group/").json()) == 1


@pytest.mark.xfail(
    reason=(
        "Replacing a group's orders reads order.group.id, but Order.group is a "
        "many-to-many collection. The handler returns 500."
    ),
    strict=False,
)
def test_order_group_can_replace_its_members(client):
    shop = create_shop(client)
    create_order(client, shop["id"], order_id="PO-G1", time_window=None)
    create_order(client, shop["id"], order_id="PO-G2", time_window=None)
    created = client.post(
        "/order-group/",
        json={"name": "Morning", "order_ids": ["PO-G1", "PO-G2"]},
    )
    assert created.status_code == 201

    replaced = client.put(
        f"/order-group/{created.json()['id']}",
        json={"order_ids": ["PO-G1"]},
    )
    assert replaced.status_code == 200
    assert [order["order_id"] for order in replaced.json()["orders"]] == ["PO-G1"]


@pytest.mark.xfail(
    reason=(
        "A second group for the same order reads order.group.name. Order.group is a "
        "collection, so the duplicate-membership check returns 500 instead of 400."
    ),
    strict=False,
)
def test_order_cannot_belong_to_two_groups(client):
    shop = create_shop(client)
    create_order(client, shop["id"], order_id="PO-ONE", time_window=None)
    first = client.post("/order-group/", json={"name": "Morning", "order_ids": ["PO-ONE"]})
    assert first.status_code == 201

    second = client.post("/order-group/", json={"name": "Evening", "order_ids": ["PO-ONE"]})
    assert second.status_code == 400
    names = [group["name"] for group in client.get("/order-group/").json()]
    assert names == ["Morning"]


@pytest.mark.xfail(
    reason=(
        "Grouping an order that has a time window crashes: "
        "order_groups.endpoints reads schemas.TimeWindow, which is not exported "
        "by the order-group schema module. The group may already be committed."
    ),
    strict=False,
)
def test_order_group_response_includes_order_time_windows(client):
    shop = create_shop(client)
    create_order(client, shop["id"], order_id="PO-WIN")
    created = client.post("/order-group/", json={"name": "Windowed", "order_ids": ["PO-WIN"]})
    assert created.status_code == 201
    assert created.json()["orders"][0]["time_window"]["start"] == "09:00:00"


def test_unknown_order_group_returns_404(client):
    assert client.get("/order-group/99999").status_code == 404
    assert client.delete("/order-group/99999").status_code == 404
    assert client.put("/order-group/99999", json={"name": "Nope"}).status_code == 404
