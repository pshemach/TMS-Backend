from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config.settings import Settings

setting = Settings()

connect_args = {}
if "sqlite" in setting.database_url:
    connect_args = {"check_same_thread": False}
    
engine = create_engine(setting.database_url, connect_args = connect_args, pool_pre_ping=True, pool_recycle=300,)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()