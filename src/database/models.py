from sqlalchemy import Column, Integer, String, Float, UniqueConstraint
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