from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from src.database import models
from src.core.matrix_manager import DistanceMatrixManager
from src.database.repository import order_crud
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from datetime import datetime
import config


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
	fixed_vehicles, free_vehicles = _split_vehicles(db, vehicles, request.get("predefined_route_ids"))

	# Fixed routes
	fixed_routes = []
	remaining_orders = orders.copy()
	for veh, route in fixed_vehicles:
		route_shop_ids = [int(s["shop_id"]) if isinstance(s, dict) else int(getattr(s, 'shop_id', s)) for s in route.shops]
		route_orders = [o for o in orders if o.shop_id in route_shop_ids]
		fixed_routes.append({
			"vehicle": veh,
			"orders": route_orders,
			"path": route_shop_ids
		})
		remaining_orders = [o for o in remaining_orders if o not in route_orders]

	# Optimize free
	optimized_routes = []
	if free_vehicles and remaining_orders:
		optimized_routes = _optimize_free_vehicles(
			db, free_vehicles, remaining_orders,
			request.get("use_time_windows", False),
			request.get("priority_orders", []) or [],
			request.get("geo_constraints", []) or []
		)

	return fixed_routes, optimized_routes


def _split_vehicles(db, vehicles, predefined_route_ids) -> Tuple[List, List]:
	fixed = []
	free = []
	used_route_ids = set(predefined_route_ids or [])

	for v in vehicles:
		if getattr(v, 'predefined_route', None) and getattr(v.predefined_route, 'id', None) in used_route_ids:
			fixed.append((v, v.predefined_route))
		else:
			free.append(v)
	return fixed, free


def _optimize_free_vehicles(db, vehicles, orders, use_time_windows, priority_orders, geo_constraints):
	shop_ids = [o.shop_id for o in orders]
	all_nodes = [1] + shop_ids  # depot = 1
	matrix_mgr = DistanceMatrixManager(db)

	distance_matrix = matrix_mgr.get_distance_matrix_as_array(all_nodes)
	time_matrix = matrix_mgr.get_time_matrix_as_array(all_nodes)
	use_time = use_time_windows and any(o.time_window_start for o in orders)
	matrix = time_matrix if use_time else distance_matrix

	# Build max_per_vehicle: when using time, interpret as minutes; otherwise distance (km)
	max_per_vehicle = []
	for v in vehicles:
		# prefer constraint table values if present
		if v.constraint:
			max_per_vehicle.append(int(v.constraint.max_distance or 300))
		else:
			# fallback default
			max_per_vehicle.append(300)

	data = {
		"matrix": matrix,
		"demands": [0] + [1] * len(shop_ids),
		"node_mapping": all_nodes,
		"num_vehicles": len(vehicles),
		"depot": 0,
		"max_per_vehicle": max_per_vehicle,
		"penalties": [10000 if str(all_nodes[i]) in (priority_orders or []) else 500 for i in range(len(all_nodes))],
		"time_windows": _build_time_windows(orders, use_time_windows),
	}

	visited, routes = _run_ortools_solver(data, vehicles, geo_constraints, None)
	return [
		{
			"vehicle": vehicles[i],
			"path": routes[i]["nodes"],
			"orders": [o for o in orders if o.shop_id in routes[i]["nodes"]]
		}
		for i in range(len(routes)) if routes[i]["nodes"]
	]


def _build_time_windows(orders, use_tw):
	if not use_tw:
		return None
	tw = {1: (0, 1440)}
	for o in orders:
		if o.time_window_start and o.time_window_end:
			# convert to minutes since midnight
			start = o.time_window_start.hour * 60 + o.time_window_start.minute
			end = o.time_window_end.hour * 60 + o.time_window_end.minute
			tw[o.shop_id] = (start, end)
	return tw


def _run_ortools_solver(data, vehicles, geo_constraints, order_groups):
	manager = pywrapcp.RoutingIndexManager(len(data["matrix"]), data["num_vehicles"], data["depot"])
	routing = pywrapcp.RoutingModel(manager)

	def transit_cb(f, t):
		fn = manager.IndexToNode(f)
		tn = manager.IndexToNode(t)
		cost = int(data["matrix"][fn][tn])
		if geo_constraints:
			from_code = str(data["node_mapping"][fn])
			to_code = str(data["node_mapping"][tn])
			try:
				veh_id = routing.ActiveVehicle(f)
			except Exception:
				veh_id = None
			for gc in geo_constraints:
				if veh_id is not None and gc.get("restrictedVehicle") == getattr(vehicles[veh_id], "vehicle_id", None):
					if {from_code, to_code} == {gc.get("fromCode"), gc.get("toCode")}:
						return 999999
		return cost

	idx = routing.RegisterTransitCallback(transit_cb)
	for v in range(data["num_vehicles"]):
		routing.SetArcCostEvaluatorOfVehicle(idx, v)

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

		# Set vehicle-specific maximum end times
		for v in range(data["num_vehicles"]):
			time_dim.CumulVar(routing.End(v)).SetMax(int(data["max_per_vehicle"][v]))
	else:
		# Fallback: create a Capacity-like dimension to cap route cost (distance)
		routing.AddDimension(idx, 0, int(max(data.get("max_per_vehicle") or [300])), True, "Capacity")
		dim = routing.GetDimensionOrDie("Capacity")
		for v in range(data["num_vehicles"]):
			dim.CumulVar(routing.End(v)).SetMax(int(data["max_per_vehicle"][v]))

	# Penalties / disjunctions: allow skipping nodes with penalty
	for i in range(1, len(data["matrix"])):
		penalty = data["penalties"][i]
		routing.AddDisjunction([manager.NodeToIndex(i)], penalty if penalty < 10000 else 0)

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
                stop.arrival_time = f"{hours:02d}:{mins:02d}"
                
                # Set departure time as arrival time + service time (assumed 15 minutes)
                dep_minutes = minutes + 15
                dep_hours = dep_minutes // 60
                dep_mins = dep_minutes % 60
                stop.departure_time = f"{dep_hours:02d}:{dep_mins:02d}"
                
            db.add(stop)

    db.commit()
    db.refresh(job)
    return job