from typing import List, Dict, Optional, Tuple, Union
from sqlalchemy.orm import Session
from src.database import models
from src.core.matrix_manager import DistanceMatrixManager
from src.database.repository import order_crud
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from datetime import datetime, time
import folium
import config


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


def _fetch_geo_constraints(db: Session) -> List[Dict]:
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


def _fetch_order_groups(orders: List[models.Order]) -> Dict[int, List[int]]:
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


def _build_penalties(orders: List[models.Order], all_nodes: List[int]) -> List[int]:
	"""Build penalty array based on order priorities from database.
	
	Penalties control whether an order can be skipped if it doesn't fit in routes:
	- HIGH priority: penalty = 100000 (must be included, cannot skip)
	- MEDIUM priority: penalty = 5000 (should be included, high cost to skip)
	- LOW priority: penalty = 500 (can skip if needed, low cost)
	- DEPOT: penalty = 0 (always included)
	
	Args:
		orders: List of order objects with priority field
		all_nodes: List of all nodes [depot, shop1, shop2, ...]
	
	Returns:
		List of penalties matching all_nodes indices
	"""
	# Create mapping of shop_id -> order priority
	shop_priority_map = {}
	for order in orders:
		priority = order.priority if hasattr(order, 'priority') and order.priority else models.Priority.MEDIUM
		
		if priority == models.Priority.HIGH:
			shop_priority_map[order.shop_id] = 100000  # Must include - emergency/urgent
		elif priority == models.Priority.LOW:
			shop_priority_map[order.shop_id] = 500     # Can skip - no urgency
		else:  # MEDIUM (default)
			shop_priority_map[order.shop_id] = 5000    # Should include - normal urgency
	
	# Build penalty array matching node order
	penalties = []
	for node in all_nodes:
		if node == 1:  # Depot
			penalties.append(0)
		else:
			penalties.append(shop_priority_map.get(node, 5000))  # Default to MEDIUM
	
	return penalties


def run_optimization_task(
	db: Session,
	request: dict,
	vehicles: List[models.Vehicles],
	orders: List[models.Order],
	job_id: Optional[int] = None,
):
	"""Run optimization and persist results.

	If job_id is provided, update that Job record instead of creating a new one.
	"""
	job = None
	try:
		if job_id:
			job = db.query(models.Job).filter(models.Job.id == job_id).first()
			if job:
				job.status = models.JobStatus.RUNNING
				db.commit()

		# Fetch geo constraints from database
		geo_constraints = _fetch_geo_constraints(db)
		
		# Fetch order groups from database
		# Orders in the same group must be assigned to the same vehicle
		order_groups = _fetch_order_groups(orders)
		
		# Store in request for easy access
		request["geo_constraints"] = geo_constraints
		request["order_groups"] = order_groups

		fixed_routes, optimized_routes = _optimize_with_predefined(db, request, vehicles, orders)

		# Save routes into provided job or create a new one
		if job:
			_save_job(db, job, fixed_routes + optimized_routes)
		else:
			job = _save_job(db, request["day"], fixed_routes + optimized_routes)

		# Mark orders as active
		order_ids = [o.id for r in (fixed_routes + optimized_routes) for o in r["orders"]]
		if order_ids:
			order_crud.mark_orders_active(order_ids, db)

		job.status = models.JobStatus.COMPLETED
		db.commit()
		print(f"Job {job.id} completed")
	except Exception as e:
		if not job:
			job = db.query(models.Job).filter(models.Job.name == f"Delivery {request['day']}").first()
		if job:
			job.status = models.JobStatus.FAILED
			db.commit()
		print(f"Optimization failed: {e}")


def _optimize_with_predefined(db, request, vehicles, orders):
	vehicle_route_mapping = request.get("vehicle_route_mapping", {})
	order_groups = request.get("order_groups", {})
	geo_constraints = request.get("geo_constraints", [])
	use_time_windows = request.get("use_time_windows", False)
	
	fixed_vehicles, free_vehicles = _split_vehicles(db, vehicles, vehicle_route_mapping)

	# Optimize predefined routes (optimize shop order but keep vehicle assignment)
	predefined_optimized_routes = []
	remaining_orders = orders.copy()
	
	for veh, route in fixed_vehicles:
		route_shop_ids = [int(s["shop_id"]) if isinstance(s, dict) else int(getattr(s, 'shop_id', s)) for s in route.shops]
		route_orders = [o for o in orders if o.shop_id in route_shop_ids]
		
		if route_orders:
			# Run optimization for this single vehicle with its assigned orders
			optimized = _optimize_single_vehicle_route(
				db, veh, route_orders,
				use_time_windows,
				geo_constraints,
				order_groups
			)
			if optimized:
				predefined_optimized_routes.append(optimized)
			
		remaining_orders = [o for o in remaining_orders if o not in route_orders]

	# Optimize free vehicles with remaining orders
	free_optimized_routes = []
	if free_vehicles and remaining_orders:
		free_optimized_routes = _optimize_free_vehicles(
			db, free_vehicles, remaining_orders,
			use_time_windows,
			geo_constraints,
			order_groups
		)

	return predefined_optimized_routes, free_optimized_routes


def _split_vehicles(db, vehicles, vehicle_route_mapping: dict) -> Tuple[List, List]:
	"""Split vehicles into fixed (with predefined routes) and free (to be optimized).
	
	Args:
		db: Database session
		vehicles: List of vehicle objects
		vehicle_route_mapping: Dict mapping vehicle_id -> predefined_route_id
	
	Returns:
		Tuple of (fixed_vehicles, free_vehicles)
		fixed_vehicles: List of (vehicle, predefined_route) tuples
		free_vehicles: List of vehicles to be optimized
	"""
	fixed = []
	free = []

	for v in vehicles:
		# Check if this vehicle has a predefined route assignment
		if v.id in vehicle_route_mapping:
			route_id = vehicle_route_mapping[v.id]
			# Fetch the predefined route
			route = db.query(models.PredefinedRoute).filter(
				models.PredefinedRoute.id == route_id
			).first()
			
			if route:
				fixed.append((v, route))
			else:
				# If route not found, treat as free vehicle
				free.append(v)
		else:
			free.append(v)
			
	return fixed, free


def _optimize_single_vehicle_route(db, vehicle, orders, use_time_windows, geo_constraints, order_groups):
	"""Optimize route for a single vehicle with assigned orders."""
	if not orders:
		return None
		
	shop_ids = [o.shop_id for o in orders]
	all_nodes = [1] + shop_ids  # depot = 1
	matrix_mgr = DistanceMatrixManager(db)

	distance_matrix = matrix_mgr.get_distance_matrix_as_array(all_nodes)
	time_matrix = matrix_mgr.get_time_matrix_as_array(all_nodes)
	
	# Check if ANY order has time window constraints in the database
	has_time_windows = any(
		o.time_window_start is not None and o.time_window_end is not None 
		for o in orders
	)
	
	# Use time matrix if time windows exist AND user enabled time window optimization
	use_time = use_time_windows and has_time_windows
	matrix = time_matrix if use_time else distance_matrix

	# Get vehicle constraints
	max_distance = 300
	max_visits = 15
	if vehicle.constraint:
		max_distance = int(vehicle.constraint.max_distance or 300)
		max_visits = int(vehicle.constraint.max_visits or 15)

	data = {
		"matrix": matrix,
		"demands": [0] + [1] * len(shop_ids),
		"node_mapping": all_nodes,
		"num_vehicles": 1,  # Single vehicle
		"depot": 0,
		"max_per_vehicle": [max_distance],
		"max_visits_per_vehicle": [max_visits],
		"penalties": _build_penalties(orders, all_nodes),
		"time_windows": _build_time_windows(orders, use_time_windows) if use_time else None,
		"use_time_matrix": use_time,  # Flag to indicate which matrix is being used
	}

	visited, routes = _run_ortools_solver(data, [vehicle], geo_constraints, order_groups)
	
	if routes and 0 in routes and routes[0]["nodes"]:
		return {
			"vehicle": vehicle,
			"path": routes[0],  # Contains nodes, arrival_times, total_distance, total_time
			"orders": orders
		}
	return None


def _optimize_free_vehicles(db, vehicles, orders, use_time_windows, geo_constraints, order_groups):
	shop_ids = [o.shop_id for o in orders]
	all_nodes = [1] + shop_ids  # depot = 1
	matrix_mgr = DistanceMatrixManager(db)

	distance_matrix = matrix_mgr.get_distance_matrix_as_array(all_nodes)
	time_matrix = matrix_mgr.get_time_matrix_as_array(all_nodes)
	
	# Check if ANY order has time window constraints in the database
	has_time_windows = any(
		o.time_window_start is not None and o.time_window_end is not None 
		for o in orders
	)
	
	# Use time matrix if time windows exist AND user enabled time window optimization
	use_time = use_time_windows and has_time_windows
	matrix = time_matrix if use_time else distance_matrix

	# Build max_per_vehicle and max_visits_per_vehicle from constraint table
	max_per_vehicle = []
	max_visits_per_vehicle = []
	
	for v in vehicles:
		# Get max_distance (or max_time if using time windows)
		if v.constraint:
			max_per_vehicle.append(int(v.constraint.max_distance or 300))
			max_visits_per_vehicle.append(int(v.constraint.max_visits or 15))
		else:
			# fallback defaults
			max_per_vehicle.append(300)
			max_visits_per_vehicle.append(15)

	data = {
		"matrix": matrix,
		"demands": [0] + [1] * len(shop_ids),
		"node_mapping": all_nodes,
		"num_vehicles": len(vehicles),
		"depot": 0,
		"max_per_vehicle": max_per_vehicle,
		"max_visits_per_vehicle": max_visits_per_vehicle,
		"penalties": _build_penalties(orders, all_nodes),
		"time_windows": _build_time_windows(orders, use_time_windows) if use_time else None,
		"use_time_matrix": use_time,  # Flag to indicate which matrix is being used
	}

	visited, routes = _run_ortools_solver(data, vehicles, geo_constraints, order_groups)
	return [
		{
			"vehicle": vehicles[i],
			"path": routes[i],  # Already contains nodes, arrival_times, total_distance, total_time
			"orders": [o for o in orders if o.shop_id in routes[i]["nodes"]]
		}
		for i in range(len(routes)) if routes[i]["nodes"]
	]


def _build_time_windows(orders, use_tw):
	"""Build time windows dictionary from orders.
	
	Args:
		orders: List of order objects
		use_tw: Boolean flag to enable time window constraints
	
	Returns:
		Dictionary mapping shop_id -> (start_minutes, end_minutes) or None
	"""
	if not use_tw:
		return None
	
	# Start with depot having full day availability
	tw = {1: (0, 1440)}  # Depot: 00:00 to 24:00 (1440 minutes)
	
	for o in orders:
		# Accept both datetime.time and string 'HH:MM[:SS]' values
		start = _to_minutes(getattr(o, "time_window_start", None))
		end = _to_minutes(getattr(o, "time_window_end", None))

		if start is not None and end is not None:
			tw[o.shop_id] = (start, end)
		else:
			# If no time window in DB (or unparsable), allow full day access
			tw[o.shop_id] = (0, 1440)
	
	return tw


def _run_ortools_solver(data, vehicles, geo_constraints, order_groups):
	manager = pywrapcp.RoutingIndexManager(len(data["matrix"]), data["num_vehicles"], data["depot"])
	routing = pywrapcp.RoutingModel(manager)

	def transit_cb(f, t):
		fn = manager.IndexToNode(f)
		tn = manager.IndexToNode(t)
		cost = int(data["matrix"][fn][tn])

		if geo_constraints:
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
			for gc in geo_constraints:
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

	# Add a Count dimension to track number of visits per vehicle
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
	if data.get("time_windows"):
		horizon = int(max(data.get("max_per_vehicle") or [1440]))
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
			v_start_min, v_end_max = 0, int(data["max_per_vehicle"][v])

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
	else:
		# Fallback: create a Capacity-like dimension to cap route cost (distance)
		routing.AddDimension(idx, 0, int(max(data.get("max_per_vehicle") or [300])), True, "Capacity")
		dim = routing.GetDimensionOrDie("Capacity")
		for v in range(data["num_vehicles"]):
			dim.CumulVar(routing.End(v)).SetMax(int(data["max_per_vehicle"][v]))

	# Add order group constraints: orders in the same group must be on the same vehicle
	if order_groups and data["num_vehicles"] > 1:
		for group_id, shop_ids in order_groups.items():
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

	solution = routing.SolveWithParameters(search_params)
	if not solution:
		return set(), {}

	return _extract_solution(manager, routing, solution, data)


def _extract_solution(manager, routing, solution, data):
    routes = {}
    time_dimension = routing.GetDimensionOrDie('Time') if data.get("time_windows") else None
    capacity_dimension = routing.GetDimensionOrDie('Capacity') if not data.get("time_windows") else None
    
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
def _save_job(db, job_or_day, routes_data):
    """Save routes into a Job.

    If job_or_day is a Job instance, use it; otherwise treat it as day and create a new Job.
    """
    if isinstance(job_or_day, models.Job):
        job = job_or_day
        job.status = models.JobStatus.RUNNING
        db.flush()
    else:
        day = job_or_day
        job = models.Job(name=f"Delivery {day}", day=day, status=models.JobStatus.RUNNING)
        db.add(job)
        db.flush()

    for r in routes_data:
        # Get path and timing data
        path = r.get("path", [])
        solver_data = path.get("nodes", []) if isinstance(path, dict) else path
        arrival_times = path.get("arrival_times", []) if isinstance(path, dict) else None
        
        route = models.JobRoute(
            job_id=job.id,
            vehicle_id=r["vehicle"].id,
            total_distance=path.get("total_distance") if isinstance(path, dict) else None,
            total_time=path.get("total_time") if isinstance(path, dict) else None
        )
        db.add(route)
        db.flush()

        # Save all stops including depot
        for seq, shop_id in enumerate(solver_data):
            stop = models.JobStop(
                route_id=route.id,
                shop_id=shop_id,
                sequence=seq
            )

            # Add timing if available
            if arrival_times and seq < len(arrival_times):
                minutes = arrival_times[seq]
                hours = minutes // 60
                mins = minutes % 60
                # Persist as proper time objects
                stop.arrival_time = time(int(hours % 24), int(mins % 60))

                # Set departure time as arrival time + service time (assumed 15 minutes)
                dep_minutes = minutes + 15
                dep_hours = dep_minutes // 60
                dep_mins = dep_minutes % 60
                stop.departure_time = time(int(dep_hours % 24), int(dep_mins % 60))

            db.add(stop)

        # Build and store Folium map for this route
        try:
            if solver_data:
                # Fetch shop details for coordinates
                shops = db.query(models.GPSMaster).filter(models.GPSMaster.id.in_(solver_data)).all()
                shop_by_id = {s.id: s for s in shops}

                coords = []
                marker_info = []
                for seq, sid in enumerate(solver_data):
                    s = shop_by_id.get(sid)
                    if not s:
                        continue
                    coords.append((s.latitude, s.longitude))
                    marker_info.append((seq, s))

                if coords:
                    # Center map roughly around route
                    avg_lat = sum(lat for lat, _ in coords) / len(coords)
                    avg_lon = sum(lon for _, lon in coords) / len(coords)
                    fmap = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, tiles="OpenStreetMap")

                    # Draw path
                    folium.PolyLine(coords, color="blue", weight=4, opacity=0.7).add_to(fmap)

                    # Add markers
                    for seq, s in marker_info:
                        is_depot = (seq == 0) or (seq == len(marker_info) - 1)
                        color = "green" if is_depot else "blue"
                        folium.CircleMarker(
                            location=[s.latitude, s.longitude],
                            radius=5,
                            color=color,
                            fill=True,
                            fill_color=color,
                            tooltip=f"Stop {seq}",
                            popup=f"{seq}: {getattr(s, 'shop_code', '') or s.location}"
                        ).add_to(fmap)

                    # Store HTML
                    route.folium_html = fmap.get_root().render()
        except Exception:
            # If map generation fails, continue without blocking job save
            route.folium_html = None

    db.commit()
    db.refresh(job)
    return job