from sqlalchemy import Column,JSON, Integer, String, Float, Date, Time, Text, UniqueConstraint, DateTime, Enum, Table, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base
from dataclasses import dataclass

@dataclass
class Depot:
    BRAND = 'depot'

class GPSMaster(Base):
    """master shop list data storage table"""
    __tablename__ = 'master_gps'
    
    id = Column(Integer, primary_key=True, index=True)
    shop_code = Column(String)
    location = Column(String)
    address = Column(String)
    brand = Column(String)
    district = Column(String)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    matrix_status = Column(String, default=None)
    
    __table_args__ = (
        UniqueConstraint('shop_code', name='_unique_shop'),
    )
    
class MatrixMaster(Base):
    """Distance matrix storage table (upper triangle only)"""
    __tablename__ = 'shop_matrix'
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id_1 = Column(Integer)
    shop_id_2 = Column(Integer)
    shop_code_1 = Column(String)
    shop_code_2 = Column(String)
    distance_km = Column(Float)
    time_minutes = Column(Float)
    coords = Column(JSON, nullable=True)
    last_calculated = Column(DateTime, default=datetime.utcnow)

class Fleets(Base):
    """Fleet data storage table"""
    __tablename__ = "fleets"
    
    id = Column(Integer, primary_key=True, index=True)
    fleet_name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    region = Column(String, nullable=False)
    manager = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total_vehicles = Column(Integer, default=0, nullable=False)
    available_vehicles = Column(Integer, default=0, nullable=False)
    
    __table_args__ = (
        CheckConstraint("available_vehicles <= total_vehicles", name="check_vehicle_counts"),
    )
    
    # Define one-to-many relationship with Vehicles
    vehicles = relationship("Vehicles", back_populates="fleet", cascade="all, delete-orphan")
    
class Vehicles(Base):
    """Vehicle data storage table"""
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_name = Column(String, nullable=False)
    fleet_id = Column(Integer, ForeignKey("fleets.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    location = Column(String)
    
    # Define relationships
    fleet = relationship("Fleets", back_populates="vehicles")
    constraint = relationship(
            "VehicleConstrain",
            back_populates="vehicle",
            uselist=False,
            cascade="all, delete-orphan"
        )
    geo_constraint = relationship(
            "GeoConstraint",
            back_populates="vehicle",
            cascade="all, delete-orphan"  
        )
    
class VehicleConstrain(Base):
    """Vehicle constraint storage table"""
    __tablename__ = "vehicle_constrains"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, unique=True)
    vehicle_name = Column(String, nullable=False)
    fleet = Column(String, nullable=False)
    type = Column(String, nullable=False)
    days = Column(Integer, default=1)
    payload = Column(Float, default=10000.0)  # kg
    volume = Column(Float, default=40.0)  # cubic meters
    time_window = Column(String, default="00:00-23:59")
    max_distance = Column(Float, default=1200.0)  # km
    max_visits = Column(Integer, default=15)
    
    # Define one-to-one relationship with Vehicles
    vehicle = relationship("Vehicles", back_populates="constraint")
    
class GeoConstraint(Base):
    __tablename__ = "geo_constraints"
    
    id = Column(Integer, primary_key=True, index=True)
    start_shop_id = Column(Integer, ForeignKey("master_gps.id"), nullable=False)
    end_shop_id   = Column(Integer, ForeignKey("master_gps.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    
    # relationships
    start_shop = relationship("GPSMaster", foreign_keys=[start_shop_id])
    end_shop   = relationship("GPSMaster", foreign_keys=[end_shop_id])
    vehicle    = relationship("Vehicles", back_populates="geo_constraint")
    # UNIQUE TOGETHER: (start, end, vehicle)
    __table_args__ = (UniqueConstraint('start_shop_id','end_shop_id','vehicle_id',name='uix_route_vehicle'),)
    
    

class PredefinedRoute(Base):
    __tablename__ = "predefined_routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    
    # Store shops as JSON: [{"shop_id": 1}, {"shop_id": 5}, ...]
    shops = Column(JSON, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint('name', name='uix_route_name'),
    )
    
# Enum for status
class OrderStatus(enum.Enum):
    PENDING = "pending"      # Not yet in optimization
    PLANED = "planed"
    ACTIVE = "active"        # In current route plan
    COMPLETED = "completed"  # Delivered
    
class Priority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("master_gps.id"), nullable=False)
    po_value = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    po_date = Column(Date, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)

    # Constraints
    time_window_start = Column(Time, nullable=True)  # e.g., 09:00:00
    time_window_end = Column(Time, nullable=True)    # e.g., 17:00:00
    priority = Column(Enum(Priority), nullable=True, default=Priority.MEDIUM)

    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)


    # Relationships
    shop = relationship("GPSMaster")
    group = relationship("OrderGroup", back_populates="orders", secondary="order_group_link")
    job = relationship("Job", back_populates="orders")  
    
    __table_args__ = (UniqueConstraint('order_id', name='uix_order_id'),)
    
class OrderGroup(Base):
    __tablename__ = "order_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)  # e.g., "Colombo Morning Batch"
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="group", secondary="order_group_link")


# --- Link Table (Many-to-Many) ---
order_group_link = Table(
    "order_group_link",
    Base.metadata,
    Column("order_id", Integer, ForeignKey("orders.id"), primary_key=True),
    Column("group_id", Integer, ForeignKey("order_groups.id"), primary_key=True),
)

class JobStatus(enum.Enum):
    RUNNING = "running"
    PLANNED = "planned"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    day = Column(Date, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PLANNED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    routes = relationship("JobRoute", back_populates="job", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="job")

class JobRoute(Base):
    __tablename__ = "job_routes"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    total_distance = Column(Float, nullable=True)
    total_time = Column(Float, nullable=True)
    
    folium_html = Column(Text, nullable=True)

    job = relationship("Job", back_populates="routes")
    vehicle = relationship("Vehicles")
    stops = relationship("JobStop", back_populates = "route", cascade="all, delete-orphan", order_by="JobStop.sequence")


class JobStop(Base):
    __tablename__ = "job_stops"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("job_routes.id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(Integer, ForeignKey("master_gps.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    order_id = Column(String, nullable=True)  # Already correct - matches Order.order_id type
    arrival_time = Column(Time, nullable=True)
    departure_time = Column(Time, nullable=True)

    route = relationship("JobRoute", back_populates="stops")
    shop = relationship("GPSMaster")
    # Add this relationship to query the order from a stop
    order = relationship("Order", foreign_keys=[order_id], 
                        primaryjoin="JobStop.order_id==Order.order_id",
                        viewonly=True)  # viewonly=True since no FK constraint