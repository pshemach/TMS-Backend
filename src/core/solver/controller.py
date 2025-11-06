from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional, Union, List, Dict, Tuple
from datetime import datetime, time
from src.database import models
from src.database.repository import order_crud
from src.core.solver.data_model import ORDataModel
from src.api import schemas
from src.core.solver.ortool_solver import VRPSolver
from src.core.map_manager import MapManager
from src.utils.map_utils import get_path_coordinates
import folium
from folium import plugins


def run_optimization_task(db: Session,request: schemas.OptimizeRequest,job_id: Optional[int]=None):
    
    job =None
    try:
        if job_id:
            job = db.query(models.Job).filter(models.Job.id == job_id).first()
        
        orchestrator = Orchestrator(db=db, request=request)
        fixed_routes, optimized_routes = orchestrator.optimize_orchestrator()
        
        if job:
            orchestrator._save_job(db, job, (fixed_routes + optimized_routes))
        else:
            job = orchestrator._save_job(db, request["day"], (fixed_routes + optimized_routes))
        
        # Mark orders as active
        order_ids = [o.id for r in (fixed_routes + optimized_routes) for o in r["orders"]]
        if order_ids:
            order_crud.mark_orders_active(order_ids, db)
            
        job.status = models.JobStatus.PLANNED
        db.commit()
    except Exception as e:
        print(f"optimization failed: {e}")


class Orchestrator:
    def __init__(self, db: Session, request: schemas.OptimizeRequest):
        self.db = db
        self.request = request
        self.free_vehicles, self.fixed_vehicles = self._split_vehicles()
        
    def optimize_orchestrator(self):
        """process uncompleted orders"""
        
        orders = self.db.query(models.Order).filter(
            models.Order.id.in_(self.request.selected_orders),
            models.Order.status != models.OrderStatus.COMPLETED
        ).all()
        remaining_orders = orders.copy()
        
        """optimize predefined route assigned vehicles"""
        predefined_optimized_routes = []
        for v, route in self.fixed_vehicles:
            route_shop_ids = []
            for r in route.shops:
                route_shop_ids.append(int(r['shop_id']))
            route_orders = [o for o in orders if o.shop_id in route_shop_ids]
            if route_orders:
                optimized = self._optimize_single_vehicle_route(vehicle=v, orders=route_orders)
                if optimized:
                    predefined_optimized_routes.append(optimized)
                    
            remaining_orders = [o for o in remaining_orders if o not in route_orders]
        
        """optimized vehicles not assigned pre routes"""
        free_optimized_routes=[]
        if self.free_vehicles and remaining_orders:
            free_optimized_routes = self._optimize_free_vehicles(orders=remaining_orders, vehicles=self.free_vehicles)
            
        return predefined_optimized_routes, free_optimized_routes
    
    
    def _split_vehicles(self):
        fixed = []
        free = []
        
        selected_vehicle_ids = [v.vehicle_id for v in self.request.vehicles]
        vehicle_route_mapping = {v.vehicle_id:v.predefined_route_id for v in self.request.vehicles if  v.predefined_route_id}
        
        vehicles = self.db.query(models.Vehicles).filter(
            models.Vehicles.id.in_(selected_vehicle_ids)
            ).all()
        
        for v in vehicles:
            if v.id in vehicle_route_mapping:
                route_id = vehicle_route_mapping[v.id]
                
                route = self.db.query(models.PredefinedRoute).filter(
                    models.PredefinedRoute.id == route_id
                    ).first()
                
                if route:
                    fixed.append((v, route))
                else:
                    free.append(v)
                    
            else:
                free.append(v)
        print(fixed, free)
        return free, fixed 
                
                
    def _optimize_single_vehicle_route(self,orders: List[models.Order], vehicle: models.Vehicles):
        data = ORDataModel(db=self.db, vehicles=[vehicle], orders=orders).get_data()
        visited, routes = VRPSolver().run_ortools_solver(data, [vehicle])
        print(routes)
        print(data)
        if routes and 0 in routes and routes[0]["nodes"]:
            return {
                "vehicle": vehicle,
                "path": routes[0],
                "orders": orders
            }
            
    def _optimize_free_vehicles(self, orders: List[models.Order], vehicles: List[models.Vehicles]):
        data = ORDataModel(db=self.db, vehicles=vehicles, orders=orders).get_data()
        print(data)
        visited, routes = VRPSolver().run_ortools_solver(data=data, vehicles=vehicles)
        print(routes)
        return [
            {
                "vehicle": vehicles[i],
			    "path": routes[i],  # Already contains nodes, arrival_times, total_distance, total_time
			    "orders": [o for o in orders if o.shop_id in routes[i]["nodes"]]
       }
            for i in range(len(routes)) if routes[i]["nodes"]
            ]
        
        
    def _save_job(self, db: Session, job_or_day, routes_data):
        """Save routes into a Job with order tracking and proper timing."""
        
        if isinstance(job_or_day, models.Job):
            job = job_or_day
            job.status = models.JobStatus.RUNNING
            db.flush()
        else:
            day = job_or_day
            job = models.Job(name=f"Delivery {day}", day=day, status=models.JobStatus.RUNNING)
            db.add(job)
            db.flush()

        print(f"\n=== SAVING JOB {job.id} WITH {len(routes_data)} ROUTES ===")

        for route_idx, r in enumerate(routes_data):
            print(f"\n--- Processing Route {route_idx + 1}/{len(routes_data)} ---")
            
            # Get path data
            path = r.get("path", {})
            solver_nodes = path.get("nodes", [])
            orders_sequence = path.get("orders", [])
            arrival_times = path.get("arrival_times", [])
            departure_times = path.get("departure_times", [])
            
            print(f"Route nodes: {solver_nodes}")
            print(f"Route orders: {[o['order_id'] for o in orders_sequence]}")
            print(f"Vehicle: {r['vehicle'].id}")
            print(f"Total distance: {path.get('total_distance')} km")
            print(f"Total time: {path.get('total_time')} minutes")
            
            # Create route record
            route = models.JobRoute(
                job_id=job.id,
                vehicle_id=r["vehicle"].id,
                total_distance=path.get("total_distance"),
                total_time=path.get("total_time")
            )
            db.add(route)
            db.flush()
            print(f"Created JobRoute with ID: {route.id}")

            # Track which order we're processing
            order_idx = 0
            
            # Save stops with order tracking and timing
            for seq, shop_id in enumerate(solver_nodes):
                # Check if this stop has an order
                order_id_value = None
                if order_idx < len(orders_sequence):
                    current_order = orders_sequence[order_idx]
                    # Only assign order_id if this shop matches the order's shop
                    if current_order["shop_id"] == shop_id:
                        order_id_value = current_order["order_id"]
                        order_idx += 1
                
                stop = models.JobStop(
                    route_id=route.id,
                    shop_id=shop_id,
                    order_id=order_id_value,
                    sequence=seq
                )

                # Add timing from calculated times
                if arrival_times and seq < len(arrival_times):
                    minutes = int(arrival_times[seq])
                    hours = minutes // 60
                    mins = minutes % 60
                    stop.arrival_time = time(int(hours % 24), int(mins % 60))
                    
                    print(f"  Stop {seq} arrival: {stop.arrival_time}")

                if departure_times and seq < len(departure_times):
                    minutes = int(departure_times[seq])
                    hours = minutes // 60
                    mins = minutes % 60
                    stop.departure_time = time(int(hours % 24), int(mins % 60))
                    
                    print(f"  Stop {seq} departure: {stop.departure_time}")

                db.add(stop)
                
                if order_id_value:
                    print(f"  Stop {seq}: shop_id={shop_id}, order_id={order_id_value}")
            
            print(f"Added {len(solver_nodes)} stops")

            # Update order status to PLANED (don't assign job_id yet)
            for order_info in orders_sequence:
                order_obj = db.query(models.Order).filter(
                    models.Order.order_id == order_info["order_id"]
                ).first()
                
                if order_obj:
                    order_obj.status = models.OrderStatus.PLANED
                    # DO NOT SET job_id here - only when job is COMPLETED
                    print(f"  Updated order {order_obj.order_id} status to PLANED")

            # Generate and store Folium map
            print(f"Generating map for route {route.id}...")
            try:
                map_manager = MapManager(db)
                map_html = map_manager.generate_map(solver_nodes)
                if map_html:
                    route.folium_html = map_html
                    print(f"✓ Map generated ({len(map_html)} chars)")
                else:
                    print(f"✗ Map generation returned None")
                    route.folium_html = None
            except Exception as e:
                print(f"✗✗✗ Map generation error: {e}")
                import traceback
                traceback.print_exc()
                route.folium_html = None

        print("\n=== COMMITTING TO DATABASE ===")
        db.commit()
        print("✓ Committed successfully")
        
        db.refresh(job)
        print(f"=== JOB {job.id} SAVED SUCCESSFULLY ===\n")
        return job
        
    def _generate_route_map(self, db: Session, solver_data: List[int]) -> Optional[str]:
        """
        Generate Folium map HTML for a route using cached paths from database.
        
        Args:
            db: Database session
            solver_data: List of shop IDs in sequence
            
        Returns:
            HTML string of the map or None if generation fails
        """
        try:
            print(f"=== STARTING MAP GENERATION ===")
            print(f"Generating map for route with {len(solver_data)} stops: {solver_data}")
            
            if not solver_data or len(solver_data) < 2:
                print("Route too short, skipping map generation")
                return None
            
            # Fetch shop details for coordinates
            shops = db.query(models.GPSMaster).filter(
                models.GPSMaster.id.in_(solver_data)
            ).all()
            
            if not shops:
                print(f"No shops found in database for IDs: {solver_data}")
                return None
            
            shop_by_id = {s.id: s for s in shops}
            print(f"Found {len(shop_by_id)} shops in database")
            
            # Get all shop coordinates
            shop_coords = []
            for sid in solver_data:
                s = shop_by_id.get(sid)
                if s:
                    shop_coords.append((s.latitude, s.longitude))
                    print(f"  Shop {sid}: ({s.latitude}, {s.longitude})")
                else:
                    print(f"Warning: Shop {sid} not found in fetched shops")
            
            if not shop_coords:
                print("No valid shop coordinates found")
                return None
            
            print(f"Got {len(shop_coords)} shop coordinates")
            
            # Center map
            avg_lat = sum(lat for lat, _ in shop_coords) / len(shop_coords)
            avg_lon = sum(lon for _, lon in shop_coords) / len(shop_coords)
            print(f"Map center: ({avg_lat}, {avg_lon})")
            fmap = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, tiles="OpenStreetMap")
            print("Folium map object created")
            
            # Get path segments between consecutive stops
            all_path_coords = []
            print(f"Processing {len(solver_data) - 1} segments...")
            
            for i in range(len(solver_data) - 1):
                origin_id = solver_data[i]
                dest_id = solver_data[i + 1]
                
                print(f"\n--- Segment {i}: {origin_id} -> {dest_id} ---")
                
                origin_shop = shop_by_id.get(origin_id)
                dest_shop = shop_by_id.get(dest_id)
                
                if not origin_shop or not dest_shop:
                    print(f"Skipping segment {origin_id} -> {dest_id}: shop not found")
                    continue
                
                # Get path from cache or OSRM
                path_coords = get_path_coordinates(
                    db=db,
                    origin_id=origin_id,
                    dest_id=dest_id,
                    origin_coords=(origin_shop.latitude, origin_shop.longitude),
                    dest_coords=(dest_shop.latitude, dest_shop.longitude)
                )
                
                if path_coords:
                    print(f"Got path with {len(path_coords)} points")
                    if len(path_coords) > 2:
                        all_path_coords.append(path_coords)
                        print(f"✓ Added segment to route")
                    else:
                        print(f"✗ Path too short ({len(path_coords)} points)")
                else:
                    print(f"✗ No path returned for {origin_id} -> {dest_id}")
            
            print(f"\n=== TOTAL PATH SEGMENTS: {len(all_path_coords)} ===")
            
            # Draw route paths with animation
            if all_path_coords:
                print("Drawing animated path segments on map...")
                for idx, segment in enumerate(all_path_coords):
                    print(f"  Drawing segment {idx} with {len(segment)} points")
                    try:
                        # Draw solid route line
                        folium.PolyLine(
                            locations=segment,
                            color="#5EFF66",  # Blue color
                            weight=6,
                            opacity=0.8,
                            popup=f"Segment {idx + 1}"
                        ).add_to(fmap)
                        
                        # Add animated ant path overlay
                        plugins.AntPath(
                            locations=segment,
                            color="#FF6B6B",  # Red color for animation
                            weight=2,
                            opacity=0.6,
                            delay=800,  # Animation speed (ms)
                            dash_array=[10, 20],  # Dash pattern
                            pulse_color="#FFFFFF"  # White pulse
                        ).add_to(fmap)
                        
                        print(f"  ✓ Segment {idx} drawn with animation successfully")
                    except Exception as e:
                        print(f"  ✗ Error drawing segment {idx}: {e}")
            else:
                print("No path coordinates available, using fallback straight lines")
                # Fallback: draw animated straight lines
                folium.PolyLine(
                    locations=shop_coords,
                    color="#5EFF66",
                    weight=6,
                    opacity=0.6,
                    dash_array='10'
                ).add_to(fmap)
                
                plugins.AntPath(
                    locations=shop_coords,
                    color="#FF6B6B",
                    weight=2,
                    opacity=0.5,
                    delay=1000,
                    dash_array=[10, 20]
                ).add_to(fmap)
            
            # Add markers for stops with custom icons
            print("Adding markers...")
            for seq, sid in enumerate(solver_data):
                s = shop_by_id.get(sid)
                if not s:
                    continue
                
                is_depot = (seq == 0) or (seq == len(solver_data) - 1)
                
                try:
                    if is_depot:
                        # Depot marker (green with home icon)
                        folium.Marker(
                            location=[s.latitude, s.longitude],
                            popup=f"🏠 DEPOT<br>{getattr(s, 'shop_code', '') or s.location}",
                            tooltip="Depot",
                            icon=folium.Icon(color='green', icon='home', prefix='fa')
                        ).add_to(fmap)
                    else:
                        # Regular stop marker with sequence number
                        icon_html = f"""
                        <div style="
                            background-color: #2E86AB;
                            color: white;
                            border-radius: 50%;
                            width: 30px;
                            height: 30px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-weight: bold;
                            font-size: 14px;
                            border: 3px solid white;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                        ">{seq}</div>
                        """
                        
                        folium.Marker(
                            location=[s.latitude, s.longitude],
                            popup=f"Stop {seq}<br>{getattr(s, 'shop_code', '') or s.location}",
                            tooltip=f"Stop {seq}",
                            icon=folium.DivIcon(html=icon_html)
                        ).add_to(fmap)
                    
                    print(f"  ✓ Marker {seq} added")
                except Exception as e:
                    print(f"  ✗ Error adding marker {seq}: {e}")
            
            # Add a legend
            legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; right: 50px; width: 200px; height: 120px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:14px; padding: 10px; border-radius: 5px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
                <h4 style="margin: 0 0 10px 0;">Legend</h4>
                <div style="margin: 5px 0;">
                    <span style="color: #5EFF66; font-weight: bold;">━━━</span> Route Path
                </div>
                <div style="margin: 5px 0;">
                    <span style="color: #FF6B6B; font-weight: bold;">- - -</span> Direction
                </div>
                <div style="margin: 5px 0;">
                    <i class="fa fa-home" style="color: green;"></i> Depot
                </div>
                <div style="margin: 5px 0;">
                    <span style="background-color: #2E86AB; color: white; 
                                 padding: 2px 6px; border-radius: 50%; font-size: 12px;">1</span> Stop
                </div>
            </div>
            '''
            fmap.get_root().html.add_child(folium.Element(legend_html))
            
            # Render HTML
            print("Rendering map to HTML...")
            html_string = fmap.get_root().render()
            print(f"✓✓✓ Generated map HTML, length: {len(html_string)} characters ✓✓✓")
            print(f"=== MAP GENERATION COMPLETE ===\n")
            
            return html_string
            
        except Exception as e:
            print(f"✗✗✗ CRITICAL ERROR in map generation: {e} ✗✗✗")
            import traceback
            traceback.print_exc()
            return None