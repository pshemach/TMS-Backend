from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import config as config
from typing import Optional, Union, List, Dict
from datetime import time


def _to_minutes(t: Optional[Union[time, str]]) -> Optional[int]:
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


class VRPSolver:
    def __init__(self):
        pass
    
    def run_ortools_solver(self, data, vehicles):
        """Main solver method with order-based time windows."""
        
        manager = pywrapcp.RoutingIndexManager(
            len(data["matrix"]), 
            data["num_vehicles"], 
            data["depot"]
        )
        routing = pywrapcp.RoutingModel(manager)
        
        # Transit callback for cost calculation
        def transit_cb(f, t):
            fn = manager.IndexToNode(f)
            tn = manager.IndexToNode(t)
            cost = int(data["matrix"][fn][tn])

            # Apply geo constraints
            if data.get('geo_constrains'):
                from_id = data["node_mapping"][fn]
                to_id = data["node_mapping"][tn]

                try:
                    veh_idx = routing.ActiveVehicle(f)
                    current_vehicle_id = vehicles[veh_idx].id if veh_idx is not None and veh_idx < len(vehicles) else None
                except Exception:
                    current_vehicle_id = None

                for gc in data['geo_constrains']:
                    restricted_vehicle = gc.get("restrictedVehicle")
                    edge_matches = {from_id, to_id} == {gc.get("fromId"), gc.get("toId")}

                    if edge_matches:
                        if restricted_vehicle is None:
                            return 999999
                        elif current_vehicle_id is not None and restricted_vehicle == current_vehicle_id:
                            return 999999

            return cost
        
        idx = routing.RegisterTransitCallback(transit_cb)
        for v in range(data["num_vehicles"]):
            routing.SetArcCostEvaluatorOfVehicle(idx, v)
        
        # Visit count dimension
        def count_cb(from_index):
            node = manager.IndexToNode(from_index)
            return 0 if node == data["depot"] else 1
        
        count_idx = routing.RegisterUnaryTransitCallback(count_cb)
        max_visits = max(data.get("max_visits_per_vehicle", [15]))
        routing.AddDimension(count_idx, 0, max_visits, True, "VisitCount")
        visit_dim = routing.GetDimensionOrDie("VisitCount")
        
        for v in range(data["num_vehicles"]):
            max_visits_for_vehicle = data.get("max_visits_per_vehicle", [15])[v]
            visit_dim.CumulVar(routing.End(v)).SetMax(max_visits_for_vehicle)
        
        # Time windows with order-based constraints
        if data.get("use_time_matrix"):
            self._add_time_dimension(routing, manager, data, vehicles, idx)
        else:
            # Fallback: distance-based dimension
            routing.AddDimension(idx, 0, int(max(data.get("max_distance_per_vehicle") or [300])), True, "Distance")
            dim = routing.GetDimensionOrDie("Distance")
            for v in range(data["num_vehicles"]):
                dim.CumulVar(routing.End(v)).SetMax(int(data["max_distance_per_vehicle"][v]))
        
        # Order group constraints
        self._add_order_group_constraints(routing, manager, data)
        
        # Penalties for skippable nodes
        self._add_penalties(routing, manager, data)
        
        # Search parameters
        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_params.time_limit.seconds = config.SOLVER_TIME_LIMIT_SECONDS
        
        try:
            routing.SetFixedCostOfAllVehicles(10000)
        except Exception:
            pass
        
        solution = routing.SolveWithParameters(search_params)
        if not solution:
            return set(), {}
        
        return self._extract_solution(manager, routing, solution, data, vehicles)
    
    def _add_time_dimension(self, routing, manager, data, vehicles, transit_idx):
        """Add time dimension with order-based time windows."""
        order_map = data.get("order_map", {})
        time_windows = data.get("time_windows", {})
        
        horizon = 1440  # 24 hours in minutes
        
        # Add time dimension with slack (waiting time allowed)
        routing.AddDimension(transit_idx, 60, horizon, False, "Time")
        time_dim = routing.GetDimensionOrDie("Time")
        
        # Set time windows for each node (order-based)
        for node_idx in range(len(data["node_mapping"])):
            index = manager.NodeToIndex(node_idx)
            
            if node_idx == 0:
                # Depot time window
                tw_data = time_windows.get(0, (data["node_mapping"][0], (0, horizon)))
                if isinstance(tw_data, tuple) and len(tw_data) == 2:
                    _, (start, end) = tw_data
                else:
                    start, end = 0, horizon
            else:
                # Order-specific time window
                order_info = order_map.get(node_idx)
                if order_info:
                    order_id = order_info['id']
                    tw_data = time_windows.get(order_id)
                    
                    if tw_data and isinstance(tw_data, tuple) and len(tw_data) == 2:
                        _, (start, end) = tw_data
                    else:
                        start, end = 0, horizon
                else:
                    start, end = 0, horizon
            
            time_dim.CumulVar(index).SetRange(int(start), int(end))
        
        # Set vehicle-specific time windows
        for v in range(data["num_vehicles"]):
            veh = vehicles[v] if v < len(vehicles) else None
            v_start_min, v_end_max = 0, horizon
            
            if veh is not None and getattr(veh, "constraint", None) is not None:
                tw_str = getattr(veh.constraint, "time_window", None)
                if isinstance(tw_str, str) and "-" in tw_str:
                    s, e = tw_str.split("-", 1)
                    s_min = _to_minutes(s.strip())
                    e_min = _to_minutes(e.strip())
                    if s_min is not None and e_min is not None:
                        v_start_min = max(0, s_min)
                        v_end_max = min(horizon, e_min)
            
            time_dim.CumulVar(routing.Start(v)).SetRange(v_start_min, v_end_max)
            time_dim.CumulVar(routing.End(v)).SetMax(v_end_max)
        
        # Add distance dimension separately when using time
        def dist_cb(f, t):
            fn = manager.IndexToNode(f)
            tn = manager.IndexToNode(t)
            return int(data["distance_matrix"][fn][tn])
        
        dist_idx = routing.RegisterTransitCallback(dist_cb)
        routing.AddDimension(dist_idx, 0, int(max(data.get("max_distance_per_vehicle") or [300])), True, "Distance")
        dist_dim = routing.GetDimensionOrDie("Distance")
        
        for v in range(data["num_vehicles"]):
            dist_dim.CumulVar(routing.End(v)).SetMax(int(data["max_distance_per_vehicle"][v]))
    
    def _add_order_group_constraints(self, routing, manager, data):
        """Add constraints to keep grouped orders on same vehicle."""
        order_groups = data.get("order_groups", {})
        order_map = data.get("order_map", {})
        
        if not order_groups or data["num_vehicles"] <= 1:
            return
        
        for group_id, shop_ids in order_groups.items():
            # Find all node indices that belong to this group
            group_node_indices = []
            
            for node_idx, order_info in order_map.items():
                if order_info['shop_id'] in shop_ids:
                    index = manager.NodeToIndex(node_idx)
                    group_node_indices.append(index)
            
            # Ensure all orders in group are on same vehicle
            if len(group_node_indices) > 1:
                first_node = group_node_indices[0]
                for other_node in group_node_indices[1:]:
                    routing.solver().Add(
                        routing.VehicleVar(first_node) == routing.VehicleVar(other_node)
                    )
    
    def _add_penalties(self, routing, manager, data):
        """Add drop penalties for non-mandatory orders."""
        for i in range(1, len(data["matrix"])):
            penalty = data["penalties"][i]
            
            # High priority (mandatory) - must be visited
            if penalty >= 10000:
                continue
            
            # Allow skipping with penalty
            routing.AddDisjunction([manager.NodeToIndex(i)], penalty)
    
    def _extract_solution(self, manager, routing, solution, data, vehicles):
        """Extract solution with order-level details."""
        routes = {}
        order_map = data.get("order_map", {})
        distance_matrix = data.get("distance_matrix")
        time_matrix = data.get("time_matrix")
        use_time_matrix = data.get("use_time_matrix", False)
        
        # Get time dimension if available
        time_dimension = None
        try:
            if data.get("time_windows"):
                time_dimension = routing.GetDimensionOrDie('Time')
        except:
            pass
        
        for v in range(routing.vehicles()):
            index = routing.Start(v)
            route_nodes = []
            order_sequence = []
            route_indices = []
            
            # Collect all nodes and indices in route
            while not routing.IsEnd(index):
                node_idx = manager.IndexToNode(index)
                shop_id = data["node_mapping"][node_idx]
                route_nodes.append(shop_id)
                route_indices.append(index)
                
                # Get order info (skip depot at index 0)
                if node_idx > 0 and node_idx in order_map:
                    order_info = order_map[node_idx].copy()
                    order_sequence.append(order_info)
                
                index = solution.Value(routing.NextVar(index))
            
            # Add final depot
            final_node_idx = manager.IndexToNode(index)
            route_nodes.append(data["node_mapping"][final_node_idx])
            route_indices.append(index)
            
            # Calculate metrics
            total_distance = 0
            total_time = 0
            arrival_times = []
            departure_times = []
            
            service_time = 15  # 15 minutes per stop
            
            for i in range(len(route_nodes)):
                if i == 0:
                    # Depot start
                    if time_dimension:
                        start_var = time_dimension.CumulVar(route_indices[i])
                        start_time = solution.Min(start_var)
                    else:
                        start_time = 480  # 8:00 AM
                    
                    arrival_times.append(start_time)
                    departure_times.append(start_time)
                    current_time = start_time
                else:
                    # Calculate travel
                    from_node = route_nodes[i - 1]
                    to_node = route_nodes[i]
                    
                    from_idx = data["node_mapping"].index(from_node)
                    to_idx = data["node_mapping"].index(to_node)
                    
                    # Distance
                    if distance_matrix:
                        travel_distance = distance_matrix[from_idx][to_idx]
                        total_distance += travel_distance
                    
                    # Time
                    if time_dimension:
                        time_var = time_dimension.CumulVar(route_indices[i])
                        current_time = solution.Min(time_var)
                    elif time_matrix:
                        travel_time = time_matrix[from_idx][to_idx]
                        current_time += travel_time
                        total_time += travel_time
                    else:
                        # Estimate from distance
                        if distance_matrix:
                            travel_time = int((distance_matrix[from_idx][to_idx] / 40) * 60)
                            current_time += travel_time
                            total_time += travel_time
                    
                    arrival_times.append(current_time)
                    
                    # Service time (except last depot)
                    if i < len(route_nodes) - 1:
                        if not time_dimension:
                            current_time += service_time
                            total_time += service_time
                    
                    departure_times.append(current_time)
            
            # Add time window info to orders
            for idx, order_info in enumerate(order_sequence):
                node_index = idx + 1  # Skip depot
                if node_index < len(arrival_times):
                    order_info['arrival_time'] = arrival_times[node_index]
                    order_info['departure_time'] = departure_times[node_index]
            
            routes[v] = {
                "nodes": route_nodes,
                "orders": order_sequence,
                "arrival_times": arrival_times,
                "departure_times": departure_times,
                "total_distance": round(total_distance, 2),
                "total_time": total_time,
                "vehicle_id": vehicles[v].id if v < len(vehicles) else None
            }
        
        return set(), routes