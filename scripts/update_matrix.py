"""CLI: process pending distance-matrix updates."""

from src.infrastructure.database.session import SessionLocal
from src.matrix.manager import DistanceMatrixManager


def usage():
    db = SessionLocal()
    manager = DistanceMatrixManager(db)
    try:
        print("=== Processing Pending Updates (with threading) ===")
        manager.process_pending_updates()

        print("\n=== Matrix Statistics ===")
        stats = manager.get_matrix_statistics()
        for key, value in stats.items():
            print(f"{key}: {value}")

        print("\n=== Getting Distance Matrix ===")
        shop_ids = [1, 2, 3, 4, 5, 6]

        distance_dict = manager.get_matrix_for_shops(shop_ids)
        print(f"Distance dict size: {len(distance_dict)}")

        distance_matrix = manager.get_distance_matrix_as_array(shop_ids)
        time_matrix = manager.get_time_matrix_as_array(shop_ids)

        print("\nDistance Matrix (km):")
        for row in distance_matrix:
            print([f"{x:.2f}" for x in row])

        print("\nTime Matrix (minutes):")
        for row in time_matrix:
            print([f"{x:.2f}" for x in row])

        dist, time = manager.get_distance(1, 5)
        print(f"\nDistance from shop 1 to shop 5: {dist:.2f} km, {time:.2f} min")

        dist, time = manager.get_distance(5, 1)
        print(f"Distance from shop 5 to shop 1: {dist:.2f} km, {time:.2f} min")
    except Exception as e:
        print(e)
    finally:
        db.close()


def get_matrix_statistics():
    """Get and display current matrix statistics."""
    db = None
    try:
        db = SessionLocal()
        manager = DistanceMatrixManager(db)
        return manager.get_matrix_statistics()
    except Exception:
        return None
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    usage()
