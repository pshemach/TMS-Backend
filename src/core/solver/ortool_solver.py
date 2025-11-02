from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import config as config
from typing import Optional, Union
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
        
        manager = pywrapcp.RoutingIndexManager(
            len(data["matrix"]), 
            data["num_vehicles"], 
            data["depot"]
            )
        routing = pywrapcp.RoutingModel(manager)
        
        def transit_cb(f, t):
            fn = manager.IndexToNode(f)
            tn = manager.IndexToNode(t)
            cost = int(data["matrix"][fn][tn])

            if data['geo_constrains']:
                # Node IDs mapped from matrix index (includes depot=1 and shop IDs)
                from_id = data["node_mapping"][fn]
                to_id = data["node_mapping"][tn]

                # Get current vehicle index
                try:
                    veh_idx = routing.ActiveVehicle(f)
                    current_vehicle_id = vehicles[veh_idx].id if veh_idx is not None and veh_idx < len(vehicles) else None
                except Exception:
                    current_vehicle_id = None

                # Check all geo constraints (undirected by default)
                for gc in data['geo_constrains']:
                    restricted_vehicle = gc.get("restrictedVehicle")

                    # ID-based match
                    edge_matches = {from_id, to_id} == {gc.get("fromId"), gc.get("toId")}

                    if edge_matches:
                        # If constraint has no specific vehicle (None), apply to all vehicles
                        if restricted_vehicle is None:
                            return 999999
                        # If constraint is for a specific vehicle, only apply to that vehicle
                        elif current_vehicle_id is not None and restricted_vehicle == current_vehicle_id:
                            return 999999

            return cost
        
        idx = routing.RegisterTransitCallback(transit_cb)
        for v in range(data["num_vehicles"]):
            routing.SetArcCostEvaluatorOfVehicle(idx, v)
            
            
        # This enforces max_visits constraint
        def count_cb(from_index):
            # Count each non-depot node as 1 visit
            node = manager.IndexToNode(from_index)
            return 0 if node == data["depot"] else 1
        
        count_idx = routing.RegisterUnaryTransitCallback(count_cb)
        max_visits = max(data.get("max_visits_per_vehicle", [15]))
        routing.AddDimension(count_idx, 0, max_visits, True, "VisitCount")
        visit_dim = routing.GetDimensionOrDie("VisitCount")
    
    	# Set vehicle-specific max visits
        for v in range(data["num_vehicles"]):
            max_visits_for_vehicle = data.get("max_visits_per_vehicle", [15])[v]
            visit_dim.CumulVar(routing.End(v)).SetMax(max_visits_for_vehicle)
        
        # If time windows provided, add Time dimension (matrix must be time values in minutes)
        if data.get("use_time_matrix"):
            horizon = int(max(data.get("max_time_per_vehicle") or [1440]))
            # allow waiting slack of up to 30 minutes
            routing.AddDimension(idx, 30, horizon, False, "Time")
            time_dim = routing.GetDimensionOrDie("Time")

            # Set time windows per node
            for node_index, node_id in enumerate(data["node_mapping"]):
                tw = data["time_windows"].get(node_id, (0, horizon))
                index = manager.NodeToIndex(node_index)
                time_dim.CumulVar(index).SetRange(tw[0], tw[1])

            # Set vehicle-specific Start/End windows combining vehicle constraints (if any)
            for v in range(data["num_vehicles"]):
                veh = vehicles[v] if v < len(vehicles) else None
                v_start_min, v_end_max = 0, int(data["max_time_per_vehicle"][v])

                # Parse vehicle time window like 'HH:MM-HH:MM'
                if veh is not None and getattr(veh, "constraint", None) is not None:
                    tw_str = getattr(veh.constraint, "time_window", None)
                    if isinstance(tw_str, str) and "-" in tw_str:
                        s, e = tw_str.split("-", 1)
                        s_min = _to_minutes(s.strip())
                        e_min = _to_minutes(e.strip())
                        if s_min is not None and e_min is not None:
                            v_start_min = max(0, s_min)
                            v_end_max = min(horizon, e_min)

                # Apply to vehicle start and end cumul vars
                time_dim.CumulVar(routing.Start(v)).SetRange(v_start_min, v_end_max)
                time_dim.CumulVar(routing.End(v)).SetMax(v_end_max)

            # Also cap distance when time windows are active
            def dist_cb(f, t):
                fn = manager.IndexToNode(f)
                tn = manager.IndexToNode(t)
                return int(data["distance_matrix"][fn][tn])
            dist_idx = routing.RegisterTransitCallback(dist_cb)
            routing.AddDimension(dist_idx, 0, int(max(data.get("max_distance_per_vehicle") or [300])), True, "Distance")
            dist_dim = routing.GetDimensionOrDie("Distance")
            for v in range(data["num_vehicles"]):
                dist_dim.CumulVar(routing.End(v)).SetMax(int(data["max_distance_per_vehicle"][v]))
        else:
            # Fallback: create a Capacity-like dimension to cap route cost (distance)
            routing.AddDimension(idx, 0, int(max(data.get("max_distance_per_vehicle") or [300])), True, "Distance")
            dim = routing.GetDimensionOrDie("Distance")
            for v in range(data["num_vehicles"]):
                dim.CumulVar(routing.End(v)).SetMax(int(data["max_distance_per_vehicle"][v]))

        # Add order group constraints: orders in the same group must be on the same vehicle
        if data["order_groups"] and data["num_vehicles"] > 1:
            for group_id, shop_ids in data["order_groups"].items():
                # Get node indices for shops in this group
                group_node_indices = []
                for shop_id in shop_ids:
                    if shop_id in data["node_mapping"]:
                        node_idx = data["node_mapping"].index(shop_id)
                        group_node_indices.append(manager.NodeToIndex(node_idx))
                
                # Add constraint: all nodes in this group must be served by the same vehicle
                # Enforce same-vehicle by equating VehicleVar across all group nodes (no precedence implied)
                if len(group_node_indices) > 1:
                    first_node = group_node_indices[0]
                    for other_node in group_node_indices[1:]:
                        routing.solver().Add(
                            routing.VehicleVar(first_node) == routing.VehicleVar(other_node)
                        )

        # Penalties / disjunctions: allow skipping nodes with penalty
        # Lower penalty = easier to skip, Higher penalty = must include
        for i in range(1, len(data["matrix"])):
            penalty = data["penalties"][i]
            # High-priority (mandatory) nodes: do NOT add a disjunction => they must be visited
            if penalty >= 10000:
                continue
            # Otherwise allow skipping with penalty
            routing.AddDisjunction([manager.NodeToIndex(i)], penalty)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_params.time_limit.seconds = config.SOLVER_TIME_LIMIT_SECONDS

        # Discourage using excess vehicles
        try:
            routing.SetFixedCostOfAllVehicles(10000)
        except Exception:
            pass

        solution = routing.SolveWithParameters(search_params)
        if not solution:
            return set(), {}

        return self._extract_solution(manager, routing, solution, data)
    
    def _extract_solution(self, manager, routing, solution, data):
        routes = {}
        time_dimension = routing.GetDimensionOrDie('Time') if data.get("time_windows") else None
        # Distance dimension is enforced separately; not required for extraction here
        
        for v in range(routing.vehicles()):
            index = routing.Start(v)
            route = []
            times = []
            total_time = 0
            total_distance = 0
            
            while not routing.IsEnd(index):
                node_idx = manager.IndexToNode(index)
                next_idx = solution.Value(routing.NextVar(index))
                next_node_idx = manager.IndexToNode(next_idx)
                
                route.append(data["node_mapping"][node_idx])
                
                if time_dimension:
                    time_var = time_dimension.CumulVar(index)
                    times.append(solution.Min(time_var))
                    # Add transit time to total
                    total_time += data["matrix"][node_idx][next_node_idx]
                
                if not routing.IsEnd(next_idx):
                    # Add distance to total
                    total_distance += data["matrix"][node_idx][next_node_idx]
                
                index = next_idx
                
            # Include the last node (return to depot)
            route.append(data["node_mapping"][manager.IndexToNode(index)])
            if time_dimension:
                time_var = time_dimension.CumulVar(index)
                times.append(solution.Min(time_var))
                
            routes[v] = {
                "nodes": route,  # Include all nodes including depot
                "arrival_times": times if time_dimension else None,
                "total_distance": total_distance,
                "total_time": total_time if time_dimension else None
            }
        
        return set(), routes