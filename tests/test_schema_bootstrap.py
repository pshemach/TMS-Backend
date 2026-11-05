"""Schema bootstrap must rebuild leftover SQLite tables from older TMS versions."""

from sqlalchemy import create_engine, inspect, text

from src.infrastructure.database.session import ensure_schema


def test_ensure_schema_rebuilds_legacy_orders_table():
    bind = create_engine("sqlite://")
    with bind.begin() as conn:
        conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, shop_id INTEGER)"))

    ensure_schema(bind=bind)

    existing = {name.lower(): name for name in inspect(bind).get_table_names()}
    assert "orders" in existing
    cols = {col["name"].lower() for col in inspect(bind).get_columns(existing["orders"])}
    assert "orderid" in cols
    assert "locationid" in cols
    assert "isdeleted" in cols
    assert "location" in existing
