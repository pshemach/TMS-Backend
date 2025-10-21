from src.core.matrix_manager import DistanceMatrixManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from config.settings import Settings

setting = Settings()


engine = create_engine(setting.database_url, connect_args = {
    "check_same_thread": False})

SessionLocal = scoped_session(sessionmaker(bind=engine))


def usage():
    db = SessionLocal()
    manager = DistanceMatrixManager(db)
    try:
        manager.process_pending_updates()
    finally:
        # db.commit()
        db.close()
        
if __name__ == "__main__":
    usage()