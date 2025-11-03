from sqlalchemy.orm import Session
from typing import Optional, Union, List, Dict
from datetime import datetime, time
from src.database import models
from src.core.matrix_manager import DistanceMatrixManager


class ORDataModel:
    def __init__(self, db: Session, vehicles: List[models.Vehicles], orders: List[models.Order], use_time_windows: bool=False, depot_id: int=1):
        self.db = db
        self.depot_id = depot_id
        
        self.shop_ids = [o.shop_id for o in orders]
        self.all_nodes = [self.depot_id] + self.shop_ids  # depot = 1
        
        self.distance_matrix, self.time_matrix = self._get_matrix(all_nodes=self.all_nodes)
        self.use_time = self._use_time_window(orders) or use_time_windows
        self.max_distance_per_vehicle, self.max_visits_per_vehicle = self._get_vehicle_constrains(vehicles=vehicles)
        self.penalties = self._build_penalties(orders=orders)
        self.time_windows = self._build_time_windows(orders=orders, use_tw=self.use_time)

        self.order_groups = self._fetch_order_groups(orders)
        self.geo_constrains = self._fetch_geo_constraints(self.db)
        
        self.matrix = self.time_matrix if self.use_time else self.distance_matrix
    
    
    def get_data(self):
        return {
            "matrix": self.matrix,
            "demands":[0] + [1]*len(self.shop_ids),
            "node_mapping":self.all_nodes,
            "num_vehicles":len(self.max_distance_per_vehicle),
            "depot": 0,
            "max_distance_per_vehicle": self.max_distance_per_vehicle,
            "max_visits_per_vehicle":self.max_visits_per_vehicle,
            "penalties":self.penalties,
            "order_groups": self.order_groups, 
            "geo_constrains": self.geo_constrains,
            "time_windows":self.time_windows,
            "use_time_matrix":self.use_time
        }
    
    def _get_matrix(self, all_nodes: List[int]):       
        matrix_mgr = DistanceMatrixManager(self.db)
        
        distance_matrix = matrix_mgr.get_distance_matrix_as_array(all_nodes)
        time_matrix = matrix_mgr.get_time_matrix_as_array(all_nodes)
        
        return distance_matrix, time_matrix
    
    def _use_time_window(self, orders: List[models.Order]):
        has_time_windows = any(
		o.time_window_start is not None and o.time_window_end is not None 
		for o in orders)
        
        return has_time_windows
    
    def _get_vehicle_constrains(self, vehicles: List[models.Vehicles]):
        max_distance_per_vehicle = []
        max_visits_per_vehicle = []
        
        for v in vehicles:
            if v.constraint:
                max_distance_per_vehicle.append(int(v.constraint.max_distance or 500))
                max_visits_per_vehicle.append(int(v.constraint.max_visits or 15))
            else:
                # fallback defaults
                max_distance_per_vehicle.append(500)
                max_visits_per_vehicle.append(15)
                
        return max_distance_per_vehicle, max_visits_per_vehicle


    def _build_time_windows(self, orders: List[models.Order], use_tw: bool):
        
        if not use_tw:
            return None
        
        tw = {self.depot_id: (0, 1440)}  # Depot: 00:00 to 24:00 (1440 minutes)
        
        for o in orders:
            start = self._to_minutes(getattr(o, "time_window_start", None))
            end = self._to_minutes(getattr(o, "time_window_end", None))
            
            if start is not None and end is not None:
                tw[o.shop_id] = (start, end)
            else:
                tw[o.shop_id] = (0, 1440)
                
        return tw
    
    
    def _build_penalties(self, orders: List[models.Order]):
        
        shop_priority_map = {}
        
        for order in orders:
            if hasattr(order, 'priority') and order.priority:
                priority = order.priority 
            else:
                priority = models.Priority.MEDIUM
            
            if priority == models.Priority.HIGH:
                shop_priority_map[order.shop_id] = 100000
                
            elif priority == models.Priority.LOW:
                shop_priority_map[order.shop_id] = 500 
                
            else:
                shop_priority_map[order.shop_id] = 5000 
        
        penalties = []       
        for node in self.all_nodes:
            if node == self.depot_id:
                penalties.append(0) 
            else:
                penalties.append(shop_priority_map.get(node, 5000)) 
                
        return penalties
    
    
    def _fetch_order_groups(self, orders: List[models.Order]) -> Dict[int, List[int]]:
        """Extract order groups from orders.
        
        Orders in the same group must be assigned to the same vehicle.
        
        Args:
            orders: List of order objects
        
        Returns:
            Dictionary mapping group_id -> [list of shop_ids in that group]
            Example: {1: [shop_5, shop_8, shop_12], 2: [shop_3, shop_7]}
        """
        order_groups = {}
        
        for order in orders:
            # Check if order belongs to any group (can be in multiple groups)
            if hasattr(order, 'group') and order.group:
                for group in order.group:
                    group_id = group.id
                    if group_id not in order_groups:
                        order_groups[group_id] = []
                    order_groups[group_id].append(order.shop_id)
            
        # Remove duplicates and return only groups with multiple orders
        filtered_groups = {}
        for group_id, shop_ids in order_groups.items():
            unique_shops = list(set(shop_ids))
            if len(unique_shops) > 1:  # Only enforce constraint if group has multiple orders
                filtered_groups[group_id] = unique_shops
        
        return filtered_groups
    
    def _fetch_geo_constraints(self, db: Session) -> List[Dict]:
        """Fetch geo constraints from database and structure them for the optimizer.
        
        Returns:
            List of geo constraint dicts with format:
            {
                "fromCode": shop_code,
                "toCode": shop_code,
                "restrictedVehicle": vehicle_id or None (None = applies to all vehicles)
            }
        """
        geo_constraints = db.query(models.GeoConstraint).all()
        
        structured_constraints = []
        for gc in geo_constraints:
            constraint = {
                # Prefer matching by IDs for correctness
                "fromId": gc.start_shop_id,
                "toId": gc.end_shop_id,
                # Keep codes for debugging/legacy if needed (not used in matching)
                "fromCode": str(gc.start_shop.shop_code) if gc.start_shop else None,
                "toCode": str(gc.end_shop.shop_code) if gc.end_shop else None,
                "restrictedVehicle": gc.vehicle_id  # None if applies to all vehicles
            }
            if constraint["fromId"] is not None and constraint["toId"] is not None:
                structured_constraints.append(constraint)
        
        return structured_constraints
                
    
    def _to_minutes(self, t: Optional[Union[time, str]]) -> Optional[int]:
        """Convert a datetime.time or 'HH:MM[:SS]' string into minutes since midnight.
        Returns None if value cannot be parsed.
        """
        if t is None:
            return None
        if isinstance(t, time):
            return t.hour * 60 + t.minute
        if isinstance(t, str):
            try:
                parts = t.split(":")
                if len(parts) >= 2:
                    h = int(parts[0])
                    m = int(parts[1])
                    return h * 60 + m
            except Exception:
                return None
        return None