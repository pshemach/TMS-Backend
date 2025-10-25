from sqlalchemy import Column,JSON, Integer, String, Float, UniqueConstraint, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

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
        UniqueConstraint('shop_code', 'brand', name='_unique_shop'),
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
    constraint = relationship("VehicleConstrain", back_populates="vehicle", uselist=False, cascade="all, delete-orphan")
    geo_constraint = relationship("GeoConstraint", back_populates="vehicle", cascade="all, delete-orphan")
    
class VehicleConstrain(Base):
    """Vehicle constraint storage table"""
    __tablename__ = "vehicle_constrains"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, unique=True)
    vehicle_name = Column(String, nullable=False)
    fleet = Column(String, nullable=False)
    type = Column(String, nullable=False)
    days = Column(Integer, default=1)
    payload = Column(Float, default=1000.0)  # kg
    volume = Column(Float, default=10.0)  # cubic meters
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