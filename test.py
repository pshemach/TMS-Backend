from src.core.matrix_manager import DistanceMatrixManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from config.settings import Settings
from src.database.database import SessionLocal

setting = Settings()


# engine = create_engine(setting.database_url, connect_args = {
#     "check_same_thread": False})

# SessionLocal = scoped_session(sessionmaker(bind=engine))


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


# """
# Matrix Update Script for MySQL
# This script can be run manually or scheduled (e.g., via cron, Windows Task Scheduler, or APScheduler)
# """
# import sys
# import logging
# from datetime import datetime
# from src.core.matrix_manager import DistanceMatrixManager
# from src.database.database import SessionLocal
# from config.settings import Settings

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('logs/matrix_update.log'),
#         logging.StreamHandler(sys.stdout)
#     ]
# )

# logger = logging.getLogger(__name__)


# def update_matrix():
#     """
#     Main function to update the distance matrix.
#     Processes all shops marked with matrix_status = 'to_update' or 'to_create'
#     """
#     db = None
#     try:
#         # Create database session
#         db = SessionLocal()
#         logger.info("=" * 60)
#         logger.info("Starting matrix update process...")
#         logger.info(f"Database URL: {Settings().database_url}")
        
#         # Initialize matrix manager
#         manager = DistanceMatrixManager(db, max_workers=10)
        
#         # Get statistics before update
#         stats_before = manager.get_matrix_statistics()
#         logger.info(f"Matrix status before update:")
#         for key, value in stats_before.items():
#             logger.info(f"  {key}: {value}")
        
#         # Process pending updates
#         logger.info("\nProcessing pending matrix updates...")
#         manager.process_pending_updates()
        
#         # Get statistics after update
#         stats_after = manager.get_matrix_statistics()
#         logger.info(f"\nMatrix status after update:")
#         for key, value in stats_after.items():
#             logger.info(f"  {key}: {value}")
        
#         # Calculate changes
#         shops_updated = stats_before['pending_updates'] - stats_after['pending_updates']
#         distances_added = stats_after['total_distances_stored'] - stats_before['total_distances_stored']
        
#         logger.info(f"\n✓ Update completed successfully!")
#         logger.info(f"  Shops processed: {shops_updated}")
#         logger.info(f"  New distances calculated: {distances_added}")
#         logger.info("=" * 60)
        
#         return True
        
#     except Exception as e:
#         logger.error(f"✗ Error during matrix update: {str(e)}", exc_info=True)
#         if db:
#             db.rollback()
#         return False
        
#     finally:
#         if db:
#             db.close()
#             logger.info("Database session closed")


# def get_matrix_statistics():
#     """
#     Get and display current matrix statistics.
#     Useful for monitoring the matrix state.
#     """
#     db = None
#     try:
#         db = SessionLocal()
#         manager = DistanceMatrixManager(db)
        
#         stats = manager.get_matrix_statistics()
        
#         logger.info("=" * 60)
#         logger.info("Current Matrix Statistics:")
#         for key, value in stats.items():
#             logger.info(f"  {key}: {value}")
#         logger.info("=" * 60)
        
#         return stats
        
#     except Exception as e:
#         logger.error(f"Error getting statistics: {str(e)}", exc_info=True)
#         return None
        
#     finally:
#         if db:
#             db.close()


# if __name__ == "__main__":
#     """
#     Run the matrix update script.
    
#     Usage:
#         python update_matrix.py          # Run full update
#         python update_matrix.py --stats  # Show statistics only
#     """
#     import argparse
    
#     parser = argparse.ArgumentParser(description='Update distance matrix for MySQL database')
#     parser.add_argument(
#         '--stats', 
#         action='store_true', 
#         help='Show matrix statistics only (no update)'
#     )
    
#     args = parser.parse_args()
    
#     if args.stats:
#         get_matrix_statistics()
#     else:
#         success = update_matrix()
#         sys.exit(0 if success else 1)