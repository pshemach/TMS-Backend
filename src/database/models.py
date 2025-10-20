from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, DateTime
from datetime import datetime
from .database import Base

class GPSMaster(Base):
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