"""ORM models — PascalCase DB columns, snake_case Python attributes."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from src.infrastructure.database.base import Base


# ---------------------------------------------------------------------------
# Enums — DB stores lowercase *values* (customer, depot), not names (CUSTOMER, DEPOT)
# ---------------------------------------------------------------------------


class LocationType(str, enum.Enum):
    CUSTOMER = "customer"
    DEPOT = "depot"


class MatrixStatus(str, enum.Enum):
    TO_CREATE = "to_create"
    TO_UPDATE = "to_update"
    UPDATED = "updated"


def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class OrderStatus(enum.Enum):
    PENDING = "pending"
    PLANED = "planed"
    ACTIVE = "active"
    COMPLETED = "completed"


class Priority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class JobStatus(enum.Enum):
    RUNNING = "running"
    PLANNED = "planned"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class SoftDeleteMixin:
    is_deleted = Column("IsDeleted", Boolean, nullable=False, default=False, index=True)
    deleted_at = Column("DeletedAt", DateTime, nullable=True)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()


class TimestampMixin:
    created_at = Column("CreatedAt", DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        "UpdatedAt",
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ---------------------------------------------------------------------------
# Location + distance matrix
# ---------------------------------------------------------------------------


class Location(Base, SoftDeleteMixin, TimestampMixin):
    """Customer or depot GPS location."""

    __tablename__ = "Location"

    id = Column("Id", Integer, primary_key=True, index=True)
    location_code = Column("LocationCode", String(50), nullable=False)
    location_name = Column("LocationName", String(100), nullable=False)
    address = Column("Address", String(255), nullable=False, default="")
    brand = Column("Brand", String(50), nullable=True)
    district = Column("District", String(100), nullable=True)
    latitude = Column("Latitude", Float, nullable=False)
    longitude = Column("Longitude", Float, nullable=False)
    location_type = Column(
        "LocationType",
        Enum(LocationType, values_callable=_enum_values, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    matrix_status = Column(
        "MatrixStatus",
        Enum(MatrixStatus, values_callable=_enum_values, native_enum=False, length=20),
        nullable=False,
        default=MatrixStatus.TO_CREATE,
    )

    __table_args__ = (
        UniqueConstraint("LocationCode", name="uq_location_code"),
    )


class DistanceMatrix(Base):
    """Upper-triangle distance / duration between two locations."""

    __tablename__ = "DistanceMatrix"

    id = Column("Id", Integer, primary_key=True, index=True)
    location_id_1 = Column("LocationId1", Integer, nullable=False, index=True)
    location_id_2 = Column("LocationId2", Integer, nullable=False, index=True)
    location_code_1 = Column("LocationCode1", String(50), nullable=False)
    location_code_2 = Column("LocationCode2", String(50), nullable=False)
    distance_km = Column("DistanceKm", Float, nullable=True)
    time_minutes = Column("TimeMinutes", Float, nullable=True)
    coords = Column("Coords", JSON, nullable=True)
    last_calculated = Column("LastCalculated", DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Fleet / vehicle
# ---------------------------------------------------------------------------


class Fleet(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "Fleet"

    id = Column("Id", Integer, primary_key=True, index=True)
    fleet_name = Column("FleetName", String(100), nullable=False)
    type = Column("Type", String(50), nullable=False)
    region = Column("Region", String(100), nullable=False)
    manager = Column("Manager", String(100), nullable=False)
    status = Column("Status", String(50), nullable=False)
    total_vehicles = Column("TotalVehicles", Integer, default=0, nullable=False)
    available_vehicles = Column("AvailableVehicles", Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "AvailableVehicles <= TotalVehicles",
            name="ck_fleet_vehicle_counts",
        ),
    )

    vehicles = relationship(
        "Vehicle",
        back_populates="fleet",
        cascade="all, delete-orphan",
    )


class Vehicle(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "Vehicle"

    id = Column("Id", Integer, primary_key=True, index=True)
    vehicle_name = Column("VehicleName", String(100), nullable=False)
    fleet_id = Column("FleetId", Integer, ForeignKey("Fleet.Id"), nullable=False, index=True)
    type = Column("Type", String(50), nullable=False)
    status = Column("Status", String(50), nullable=False)
    location = Column("Location", String(100), nullable=True)

    fleet = relationship("Fleet", back_populates="vehicles")
    constraint = relationship(
        "VehicleConstraint",
        back_populates="vehicle",
        uselist=False,
        cascade="all, delete-orphan",
    )
    geo_constraint = relationship(
        "GeoConstraint",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )


class VehicleConstraint(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "VehicleConstraint"

    id = Column("Id", Integer, primary_key=True, index=True)
    vehicle_id = Column(
        "VehicleId",
        Integer,
        ForeignKey("Vehicle.Id"),
        nullable=False,
        unique=True,
    )
    vehicle_name = Column("VehicleName", String(100), nullable=False)
    fleet = Column("Fleet", String(100), nullable=False)
    type = Column("Type", String(50), nullable=False)
    days = Column("Days", Integer, default=1)
    payload = Column("Payload", Float, default=10000.0)
    volume = Column("Volume", Float, default=40.0)
    time_window = Column("TimeWindow", String(20), default="00:00-23:59")
    max_distance = Column("MaxDistance", Float, default=1200.0)
    max_visits = Column("MaxVisits", Integer, default=15)

    vehicle = relationship("Vehicle", back_populates="constraint")


class GeoConstraint(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "GeoConstraint"

    id = Column("Id", Integer, primary_key=True, index=True)
    start_location_id = Column(
        "StartLocationId",
        Integer,
        ForeignKey("Location.Id"),
        nullable=False,
    )
    end_location_id = Column(
        "EndLocationId",
        Integer,
        ForeignKey("Location.Id"),
        nullable=False,
    )
    vehicle_id = Column("VehicleId", Integer, ForeignKey("Vehicle.Id"), nullable=True)

    start_location = relationship("Location", foreign_keys=[start_location_id])
    end_location = relationship("Location", foreign_keys=[end_location_id])
    vehicle = relationship("Vehicle", back_populates="geo_constraint")

    __table_args__ = (
        UniqueConstraint(
            "StartLocationId",
            "EndLocationId",
            "VehicleId",
            name="uq_geo_route_vehicle",
        ),
    )


class PredefinedRoute(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "PredefinedRoute"

    id = Column("Id", Integer, primary_key=True, index=True)
    name = Column("Name", String(100), nullable=False, unique=True)
    # [{"location_id": 1}, {"location_id": 5}, ...]
    locations = Column("Locations", JSON, nullable=False, default=list)

    __table_args__ = (UniqueConstraint("Name", name="uq_predefined_route_name"),)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class Order(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "Orders"

    id = Column("Id", Integer, primary_key=True, index=True)
    order_id = Column("OrderId", String(100), unique=True, nullable=False, index=True)
    location_id = Column(
        "LocationId",
        Integer,
        ForeignKey("Location.Id"),
        nullable=False,
    )
    po_value = Column("PoValue", Float, nullable=True)
    volume = Column("Volume", Float, nullable=True)
    po_date = Column("PoDate", Date, nullable=False)
    status = Column(
        "Status",
        Enum(OrderStatus),
        nullable=False,
        default=OrderStatus.PENDING,
        index=True,
    )
    time_window_start = Column("TimeWindowStart", Time, nullable=True)
    time_window_end = Column("TimeWindowEnd", Time, nullable=True)
    priority = Column(
        "Priority",
        Enum(Priority),
        nullable=True,
        default=Priority.MEDIUM,
    )
    job_id = Column(
        "JobId",
        Integer,
        ForeignKey("Job.Id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    location = relationship("Location")
    group = relationship(
        "OrderGroup",
        back_populates="orders",
        secondary="OrderGroupLink",
    )
    job = relationship("Job", back_populates="orders")

    __table_args__ = (UniqueConstraint("OrderId", name="uq_order_id"),)


class OrderGroup(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "OrderGroup"

    id = Column("Id", Integer, primary_key=True, index=True)
    name = Column("Name", String(100), nullable=False, unique=True)

    orders = relationship(
        "Order",
        back_populates="group",
        secondary="OrderGroupLink",
    )


order_group_link = Table(
    "OrderGroupLink",
    Base.metadata,
    Column("OrderId", Integer, ForeignKey("Orders.Id"), primary_key=True),
    Column("GroupId", Integer, ForeignKey("OrderGroup.Id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class Job(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "Job"

    id = Column("Id", Integer, primary_key=True, index=True)
    name = Column("Name", String(100), nullable=False)
    day = Column("Day", Date, nullable=False)
    status = Column(
        "Status",
        Enum(JobStatus),
        default=JobStatus.PLANNED,
        nullable=False,
    )

    routes = relationship(
        "JobRoute",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    orders = relationship("Order", back_populates="job")


class JobRoute(Base, TimestampMixin):
    __tablename__ = "JobRoute"

    id = Column("Id", Integer, primary_key=True, index=True)
    job_id = Column(
        "JobId",
        Integer,
        ForeignKey("Job.Id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id = Column("VehicleId", Integer, ForeignKey("Vehicle.Id"), nullable=False)
    total_distance = Column("TotalDistance", Float, nullable=True)
    total_time = Column("TotalTime", Float, nullable=True)
    folium_html = Column("FoliumHtml", LONGTEXT, nullable=True)

    job = relationship("Job", back_populates="routes")
    vehicle = relationship("Vehicle")
    stops = relationship(
        "JobStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="JobStop.sequence",
    )


class JobStop(Base, TimestampMixin):
    __tablename__ = "JobStop"

    id = Column("Id", Integer, primary_key=True, index=True)
    route_id = Column(
        "RouteId",
        Integer,
        ForeignKey("JobRoute.Id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id = Column(
        "LocationId",
        Integer,
        ForeignKey("Location.Id"),
        nullable=False,
    )
    sequence = Column("Sequence", Integer, nullable=False)
    order_id = Column("OrderId", String(100), nullable=True)
    arrival_time = Column("ArrivalTime", Time, nullable=True)
    departure_time = Column("DepartureTime", Time, nullable=True)

    route = relationship("JobRoute", back_populates="stops")
    location = relationship("Location")
    order = relationship(
        "Order",
        foreign_keys=[order_id],
        primaryjoin="JobStop.order_id==Order.order_id",
        viewonly=True,
    )


# ---------------------------------------------------------------------------
# Back-compat aliases (temporary import shims during refactor)
# ---------------------------------------------------------------------------

# Prefer importing Location / DistanceMatrix / Fleet / Vehicle directly.
GPSMaster = Location
MatrixMaster = DistanceMatrix
Fleets = Fleet
Vehicles = Vehicle
VehicleConstrain = VehicleConstraint
