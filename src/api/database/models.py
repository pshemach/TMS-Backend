from sqlalchemy import Column, Integer, String, Float
from .database import Base

class GPSMaster(Base):
    __tablename__ = 'master_gps'
    
    id = Column(Integer, primary_key=True, index=True)
    shop_code = Column(String, unique=True, nullable=False)
    location = Column(String)
    address = Column(String)
    brand = Column(String)
    district = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)