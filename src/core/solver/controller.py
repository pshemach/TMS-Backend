from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional, Union, List, Dict, Tuple
from datetime import datetime, time
from src.database import models
from src.database.repository import order_crud
from src.core.solver.data_model import ORDataModel
from src.api import schemas
from src.core.solver.ortool_solver import VRPSolver
import folium


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
        
        
        