from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, DateTime, ForeignKey
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
    """fleet data storage table"""
    __tablename__ = "fleets"
    
    id = Column(Integer, primary_key=True, index=True)
    fleet_name = Column(String)
    type = Column(String)
    region = Column(String)
    manager = Column(String)
    status = Column(String, default='active')
    total_vehicles = Column(Integer, default=0)
    available_vehicles = Column(Integer, default=0)
    # Relationship: One fleet has many vehicles
    vehicles = relationship("Vehicles", back_populates="fleet", cascade="all, delete-orphan")
    
    
class Vehicles(Base):
    """vehicle data storage table"""
    
    __tablename__ = 'vehicles'
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_name = Column(String)
    fleet_id = Column(Integer, ForeignKey('fleets.id', ondelete='CASCADE'), nullable=False)
    type = Column(String)
    status = Column(String, default='available')
    location = Column(String)
    
    # Relationships
    fleet = relationship("Fleets", back_populates="vehicles")
    constraint = relationship("VehicleConstrain", back_populates="vehicle", uselist=False, cascade="all, delete-orphan")
    
    
    
class VehicleConstrain(Base):
    """Vehicle constraint storage table"""
    __tablename__ = 'vehicle_constrains'
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id', ondelete='CASCADE'), unique=True, nullable=False)
    vehicle_name = Column(String)
    fleet = Column(String)
    type = Column(String)
    payload = Column(Float, default=1000.0)  # kg
    volume = Column(Float, default=10.0)  # cubic meters
    time_window = Column(String, default='08:00-18:00')
    max_distance = Column(Float, default=200.0)  # km
    max_visits = Column(Integer, default=12)
    
    # Relationship
    vehicle = relationship("Vehicles", back_populates="constraint")