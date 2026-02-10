from src.core.matrix_manager import DistanceMatrixManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from config.settings import Settings
from src.database.database import SessionLocal

setting = Settings()

def usage():
    db = SessionLocal()
    manager = DistanceMatrixManager(db)
    try:
        # Process pending updates with threading
        print("=== Processing Pending Updates (with threading) ===")
        manager.process_pending_updates()
        
        # Get statistics
        print("\n=== Matrix Statistics ===")
        stats = manager.get_matrix_statistics()
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        # Get distance matrix for specific shops
        print("\n=== Getting Distance Matrix ===")
        shop_ids = [1, 2, 3, 4, 5, 6]
        
        # Option 1: As dictionary
        distance_dict = manager.get_matrix_for_shops(shop_ids)
        print(f"Distance dict size: {len(distance_dict)}")
        
        # Option 2: As 2D array for OR-Tools
        distance_matrix = manager.get_distance_matrix_as_array(shop_ids)
        time_matrix = manager.get_time_matrix_as_array(shop_ids)
        
        print(f"\nDistance Matrix (km):")
        for row in distance_matrix:
            print([f"{x:.2f}" for x in row])
        
        print(f"\nTime Matrix (minutes):")
        for row in time_matrix:
            print([f"{x:.2f}" for x in row])
        
        # Get specific distance
        dist, time = manager.get_distance(1, 5)
        print(f"\nDistance from shop 1 to shop 5: {dist:.2f} km, {time:.2f} min")
        
        # This returns the SAME data (no separate B→A storage)
        dist, time = manager.get_distance(5, 1)
        print(f"Distance from shop 5 to shop 1: {dist:.2f} km, {time:.2f} min")
    except Exception as e:
        print(e)
        
    finally:
        db.close()
        
def get_matrix_statistics():
    """
    Get and display current matrix statistics.
    Useful for monitoring the matrix state.
    """
    db = None
    try:
        db = SessionLocal()
        manager = DistanceMatrixManager(db)
        
        stats = manager.get_matrix_statistics()
        
        # logger.info("=" * 60)
        # logger.info("Current Matrix Statistics:")
        # for key, value in stats.items():
        #     logger.info(f"  {key}: {value}")
        # logger.info("=" * 60)
        
        return stats
        
    except Exception as e:
        # logger.error(f"Error getting statistics: {str(e)}", exc_info=True)
        return None
        
    finally:
        if db:
            db.close()
        
if __name__ == "__main__":
    usage()
    # stats = get_matrix_statistics()
    # print(stats)


