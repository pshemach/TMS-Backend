# """
# Class-based VRP Solver using Google OR-Tools.
# Encapsulates solver logic for single-day vehicle routing.
# """

# from ortools.constraint_solver import pywrapcp, routing_enums_pb2
# from src.data_model.vrp_data_model import VRPDataModel
# import config

# class VRPSolver:
#     def __init__(self):
#         self.metric_name = "distance"
#         self.unit = "km"

#     def solve_day(self, data, day):

#         manager = pywrapcp.RoutingIndexManager(len(data["distance_matrix"]), data["num_vehicles"], data["depot"])
#         routing = pywrapcp.RoutingModel(manager)

#         # Register transit callback
#         def distance_callback(from_index, to_index):
#             from_node = manager.IndexToNode(from_index)
#             to_node = manager.IndexToNode(to_index)
#             distance = int(data["distance_matrix"][from_node][to_node])  # Use distance instead of time
#             return distance

#         transit_callback_index = routing.RegisterTransitCallback(distance_callback)
#         routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

#         # Add distance dimension
#         routing.AddDimension(
#             transit_callback_index,
#             0,
#             max(data["max_distance_per_vehicle"]),  
#             True,
#             "Distance"
#         )

#         distance_dimension = routing.GetDimensionOrDie("Distance")
#         for vehicle_id in range(data["num_vehicles"]):
#             end_index = routing.End(vehicle_id)
#             distance_dimension.CumulVar(end_index).SetMax(data["max_distance_per_vehicle"][vehicle_id])  # Set distance limit


#         # Add demand/capacity dimension
#         def demand_callback(from_index):
#             return data["demands"][manager.IndexToNode(from_index)]

#         demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
#         routing.AddDimensionWithVehicleCapacity(
#             demand_callback_index,
#             0,
#             data["max_visits_per_vehicle"],
#             True,
#             "Visits"
#         )

#         for node in range(1, len(data["distance_matrix"])):
#             routing.AddDisjunction([manager.NodeToIndex(node)], data["penalties"][node])

#         # Set search parameters
#         search_params = pywrapcp.DefaultRoutingSearchParameters()
#         search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
#         search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
#         search_params.time_limit.seconds = config.SOLVER_TIME_LIMIT_SECONDS

#         solution = routing.SolveWithParameters(search_params)

#         if solution:
#             return self._parse_solution(manager, routing, solution, data, day)
#         print(f"\u274c No solution found for Day {day + 1}!")
#         return set(), {}

#     def _parse_solution(self, manager, routing, solution, data, day):
#         total_metric = 0
#         visited_nodes = set()
#         route_dict = {}

#         metric_name = self.metric_name
#         max_metric_name = f"max_{metric_name}_per_vehicle"
#         unit = self.unit

#         print(f"\nDay {day + 1} Routes:")

#         for vehicle_id in range(data["num_vehicles"]):
#             index = routing.Start(vehicle_id)
#             route_output = f"Route for vehicle {vehicle_id}:\n"
#             route_metric = 0
#             num_visits = 0
#             route_nodes = []
#             previous_node = None

#             while not routing.IsEnd(index):
#                 node = manager.IndexToNode(index)
#                 original_node = data["node_mapping"][node]
#                 visited_nodes.add(original_node)
#                 route_nodes.append(original_node)
#                 route_output += f" {original_node} ->"

#                 if previous_node is not None:
#                     arc = int(data[f"{metric_name}_matrix"][previous_node][node])
#                     route_metric += arc

#                 previous_node = node
#                 index = solution.Value(routing.NextVar(index))

#                 if original_node != data["depot"]:
#                     num_visits += 1

#             # End node (return to depot)
#             node = manager.IndexToNode(index)
#             original_node = data["node_mapping"][node]
#             visited_nodes.add(original_node)
#             route_nodes.append(original_node)

#             route_output += f" {original_node}\n"

#             if previous_node is not None:
#                 arc = int(data[f"{metric_name}_matrix"][previous_node][node])
#                 route_metric += arc

#             max_metric = data[max_metric_name][vehicle_id]
#             route_output += f"{metric_name.capitalize()} of route: {route_metric} {unit} (Max: {max_metric})\n"
#             route_output += f"Stops visited: {num_visits - 1}/{data['max_visits_per_vehicle'][vehicle_id]}\n"

#             route_dict[vehicle_id] = {
#                 "route_nodes": route_nodes,
#                 f"route_{metric_name}": route_metric,
#                 f"max_{metric_name}_limit": max_metric,
#                 "within_limit": route_metric <= max_metric,
#                 "num_visits": num_visits - 1,
#                 "max_visits_limit": data["max_visits_per_vehicle"][vehicle_id]
#             }

#             print(route_output)
#             total_metric = max(total_metric, route_metric)

#         print(f"Max route {metric_name} for Day {day + 1}: {total_metric} {unit}\n")
#         return visited_nodes, route_dict