from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
from datetime import datetime
from src.utils.master_utils import get_osrm_data
from src.database.models import GPSMaster, MatrixMaster
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class DistanceMatrixManager:
    """Manager class for distance matrix operations with threading support"""
    
    def __init__(self, db_session: Session, max_workers: int = 10):
        self.db = db_session
        self.max_workers = max_workers
        self._lock = threading.Lock()  # For thread-safe database operations
        
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
        """
        Calculate distance and time between two GPS coordinates using OSRM.
        Returns (distance_km, duration_minutes).
        """
        _, distance, duration = get_osrm_data((lat1,lon1), (lat2,lon2))
        
        return distance, duration
    
    def process_pending_updates(self):
        """
        Process all shops marked with matrix_status = 'to_update' or 'to_create'.
        Calculate distances, duration and update matrix_status to 'updated'.
        Uses threading for faster processing.
        """
        db = self.db
        pending_shops = db.query(GPSMaster).filter(
            (GPSMaster.matrix_status == 'to_update') | 
            (GPSMaster.matrix_status == 'to_create')
        ).all()
        
        if not pending_shops:
            print("No pending updates found.")
            return 0

        # Get all shops that are already in the matrix (status = 'updated')
        existing_shops = db.query(GPSMaster).filter(
            GPSMaster.matrix_status == 'updated'
        ).all()
        
        print(f"Processing {len(pending_shops)} pending shops with {len(existing_shops)} existing shops...")
        print(f"Using {self.max_workers} worker threads for parallel processing")
        
        total_calculations = 0
        
        for pending_shop in pending_shops:
            print(f"\nProcessing shop: {pending_shop.shop_code} (ID: {pending_shop.id})")
            
            # Delete old distances if this shop was previously in matrix
            self._delete_shop_distances(pending_shop.id, db)
            
            # Calculate distances to all existing shops (with threading)
            distances_added = self._add_shop_to_matrix_threaded(
                pending_shop, 
                existing_shops
            )
            
            # Also calculate distances to other pending shops
            # Add to a list to avoid duplicate calculations
            other_pending = [s for s in pending_shops if s.id > pending_shop.id]
            
            if other_pending:
                pending_distances = self._calculate_distances_threaded(
                    pending_shop, 
                    other_pending
                )
                
                distances_added += len(pending_distances)
                
            # # NOW commit all changes for this shop
            # try:
            #     self.db.commit()
            #     print(f"\n✓ Committed {distances_added} distances to database")
            # except Exception as e:
            #     print(f"\n✗ Error committing to database: {e}")
            #     self.db.rollback()
            #     continue
            
            # Update status to 'updated'
            pending_shop.matrix_status = 'updated'
            total_calculations += distances_added
            
            print(f"✓ Total added for this shop: {total_calculations} distance calculations")
        
        # Final commit for status updates
        db.commit()
        
    def _delete_shop_distances(self, shop_id: int, db: Session) -> None:
        """Delete all distance entries for a specific shop"""
        db.query(MatrixMaster).filter(
            (MatrixMaster.shop_id_1 == shop_id )|
            (MatrixMaster.shop_id_2 == shop_id)
        ).delete(synchronize_session=False)
        db.commit()
        
    def _add_shop_to_matrix_threaded(self, new_shop: GPSMaster, existing_shops: List[GPSMaster] ) -> int:
        """
        Add a new shop to the matrix by calculating distances to all existing shops.
        Uses threading for parallel distance calculations.
        Returns count of distances added.
        """
        if not existing_shops:
            return 0
        
        distance_results = self._calculate_distances_threaded(new_shop, existing_shops)

        return len(distance_results)
    
    def _calculate_distances_threaded(self, source_shop: GPSMaster, target_shops: List[GPSMaster]) -> List[Dict]:
        """
        Calculate distances from source_shop to all target_shops using threading.
        Returns list of distance results.
        """
        distance_results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all distance calculation tasks
            future_to_shop = {
                executor.submit(
                    self._calculate_single_distance, 
                    source_shop, 
                    target_shop
                ): target_shop 
                for target_shop in target_shops
            }
                
            # Collect results as they complete
            for future in as_completed(future_to_shop):
                target_shop = future_to_shop[future]
                try:
                    result = future.result()
                    if result:
                        distance_results.append(result)
                except Exception as e:
                    print(f"  ✗ Error calculating distance to {target_shop.shop_code}: {e}")

        # Save all results to database AFTER all calculations complete
        for result in distance_results:
            self._save_distance_to_db(result)
            
        return distance_results
    def _calculate_single_distance(self, shop1: GPSMaster, shop2: GPSMaster) -> Dict:
        """
        Calculate distance between two shops.
        Returns dictionary with calculation results.
        """
        try:
            distance, time = self.calculate_distance(
                shop1.latitude, shop1.longitude,
                shop2.latitude, shop2.longitude
            )
            
            return {
                'shop_id_1': shop1.id,
                'shop_id_2': shop2.id,
                'shop_code_1': shop1.shop_code,
                'shop_code_2': shop2.shop_code,
                'distance_km': distance,
                'time_minutes': time
            }
        except Exception as e:
            print(f"  ✗ Error calculating {shop1.shop_code} → {shop2.shop_code}: {e}")
            return None
        
        
    def _save_distance_to_db(self, distance_data: Dict) -> None:
        """
        Save distance to database in a thread-safe manner.
        IMPORTANT: Does NOT store both A→B and B→A, only stores once.
        """
        db = self.db
        # Ensure we always store with shop_id_1 < shop_id_2 (upper triangle)
        sid1 = min(distance_data['shop_id_1'], distance_data['shop_id_2'])
        sid2 = max(distance_data['shop_id_1'], distance_data['shop_id_2'])
        
        # Get corresponding shop codes in correct order
        if distance_data['shop_id_1'] == sid1:
            scode1 = distance_data['shop_code_1']
            scode2 = distance_data['shop_code_2']
        else:
            scode1 = distance_data['shop_code_2']
            scode2 = distance_data['shop_code_1']
        
        # Check if this distance pair already exists
        existing = self.db.query(MatrixMaster).filter(
            MatrixMaster.shop_id_1 == sid1,
            MatrixMaster.shop_id_2 == sid2
        ).first()
        

        if existing:
            # Update existing record
            existing.distance_km = distance_data['distance_km']
            existing.time_minutes = distance_data['time_minutes']
            existing.last_calculated = datetime.utcnow()
            print(f"  ✓ Updated: {scode1} ↔ {scode2} = {distance_data['distance_km']:.2f} km")
        else:
            # Create new record
            new_distance = MatrixMaster(
                shop_id_1=sid1,
                shop_id_2=sid2,
                shop_code_1=scode1,
                shop_code_2=scode2,
                distance_km=distance_data['distance_km'],
                time_minutes=distance_data['time_minutes'],
                last_calculated=datetime.utcnow()
            )
            db.add(new_distance)
            print(f"  ✓ Added: {scode1} ↔ {scode2} = {distance_data['distance_km']:.2f} km")
        db.commit()

    def get_distance(self, shop_id_1: int, shop_id_2: int) -> Tuple[float, float]:
        """
        Get distance between two shops from database.
        Handles both A→B and B→A by checking in correct order.
    
        Returns: (distance_km, time_minutes) or (None, None) if not found
        """
        
        if shop_id_1 == shop_id_2:
            return 0.0, 0.0
        
        sid1 = min(shop_id_1, shop_id_2)
        sid2 = max(shop_id_1, shop_id_2)
        
        result = self.db.query(MatrixMaster).filter(
            MatrixMaster.shop_id_1 == sid1 ,
            MatrixMaster.shop_id_2 == sid2
        ).first()
        
        if result:
            return result.distance_km, result.time_minutes
        
        return None, None
    
    def get_matrix_for_shops(self, shop_ids:List[int]) -> Dict[Tuple[int, int], Dict]:
        """
        Get distance matrix for specific shop IDs.
        Returns dictionary with (shop_id_1, shop_id_2) as key.
        Automatically handles symmetry: if you query B→A, returns A→B data.
        
        Returns: {(shop_id_1, shop_id_2): {'distance': X, 'time': Y}}
        """
        
        n = len(shop_ids)
        distance_dict = {}
    
        # Add zero distances for same shop
        for shop_id in shop_ids:
            distance_dict[(shop_id, shop_id)] = {'distance': 0.0, 'time': 0.0}
    
        # Query all distances for these shops
        for i, shop_id_1 in enumerate(shop_ids):
            for shop_id_2 in shop_ids[i+1:]:
                distance, time = self.get_distance(shop_id_1, shop_id_2)
    
                if distance is not None:

                    distance_dict[(shop_id_1, shop_id_2)] = {
                        'distance': distance, 'time': time
                    }
                    
                    distance_dict[(shop_id_2, shop_id_1)] = {
                        'distance': distance, 'time': time
                    }
                       
        return distance_dict
    
    def get_distance_matrix_as_array(self, shop_ids: List[int]) -> List[List[float]]:
        """
        Get distance matrix as 2D array.
        
        Returns: 2D list where matrix[i][j] = distance from shop_ids[i] to shop_ids[j]
        """
        
        n = len(shop_ids)
        
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        
        distance_dict = self.get_matrix_for_shops(shop_ids)
     
        for i, shop_id_1 in enumerate(shop_ids):
            for j, shop_id_2 in enumerate(shop_ids):
                if (shop_id_1, shop_id_2) in distance_dict:
                    matrix[i][j] = distance_dict[(shop_id_1, shop_id_2)]['distance']
                    
        return matrix
    
    
    def get_time_matrix_as_array(self, shop_ids: List[int]) -> List[List[float]]:
        """
        Get time matrix as 2D array.
        
        Returns: 2D list where matrix[i][j] = time from shop_ids[i] to shop_ids[j]
        """
        n = len(shop_ids)
        
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        
        distance_dict = self.get_matrix_for_shops(shop_ids)
        
        for i, shop_id_1 in enumerate(shop_ids):
            for j, shop_id_2 in enumerate(shop_ids):
                if (shop_id_1, shop_id_2) in distance_dict:
                    matrix[i][j] = distance_dict[(shop_id_1, shop_id_2)]['time']
                    
        return matrix
    
    def get_matrix_statistics(self) -> Dict:
        """Get statistics about the current matrix"""
        total_shops = self.db.query(GPSMaster).filter(
            GPSMaster.matrix_status == 'updated'
        ).count()
        
        pending_shops = self.db.query(GPSMaster).filter(
            (GPSMaster.matrix_status == 'to_update') |
            (GPSMaster.matrix_status == 'to_create')
        ).count()
        
        total_distances = self.db.query(MatrixMaster).count()
        
        # Expected distances for upper triangle: n*(n-1)/2
        expected_distances = (total_shops * (total_shops - 1)) / 2 if total_shops > 0 else 0
        
        return {
            'total_shops_in_matrix': total_shops,
            'pending_updates': pending_shops,
            'total_distances_stored': total_distances,
            'expected_distances': int(expected_distances),
            'matrix_completeness': f"{(total_distances/expected_distances*100):.1f}%" if expected_distances > 0 else "N/A"
        }