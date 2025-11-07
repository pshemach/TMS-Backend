from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional, Union, List, Dict, Tuple
from datetime import time
from src.database import models
from src.database.repository import order_crud
from src.core.solver.data_model import ORDataModel
from src.api import schemas
from src.core.solver.ortool_solver import VRPSolver
from src.core.map_manager import MapManager
from src.logger import logging
from src.exception import TMSException
import sys

def run_optimization_task(db: Session,request: schemas.OptimizeRequest,job_id: Optional[int]=None):
    try:

        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            logging.debug(f"Job with id {job_id} has not found")
            raise TMSException(f"Job with id {job_id} has not found", sys)
        
        orchestrator = Orchestrator(db=db, request=request)
        fixed_routes, optimized_routes = orchestrator.optimize_orchestrator()
        
        # Save route data in database
        all_routes = (fixed_routes + optimized_routes)
        _ = orchestrator._save_job(db, job, all_routes)
        
        # Update planed orders status
        order_ids = [o.id for r in all_routes for o in r["orders"]]
        if order_ids:
            order_crud.mark_orders_planed(order_ids, db)
            logging.info("Changed order status: 'planed'")
            
    except Exception as e:
        logging.error(f"optimization failed: {e}")
        raise TMSException(e, sys)


class Orchestrator:
    def __init__(self, db: Session, request: schemas.OptimizeRequest):
        self.db = db
        self.request = request
        (self.free_vehicles, self.fixed_vehicles) = self._split_vehicles()
        
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
        try:
            fixed = []
            free = []
            
            selected_vehicle_ids = [v.vehicle_id for v in self.request.vehicles]
            vehicle_route_mapping = {v.vehicle_id:v.predefined_route_id for v in self.request.vehicles if  v.predefined_route_id}
            
            vehicles = self.db.query(models.Vehicles).filter(
                models.Vehicles.id.in_(selected_vehicle_ids)
                ).all()
            
            logging.info(f"Total vehicles for optimization: {len(vehicles)}")
            
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
                    
            logging.info(f"Predefined routes assigned vehicles: {len(fixed)}")
            logging.info(f"Number of free vehicles: {len(free)}")
            
            return (free, fixed )
        except Exception as e:
            logging.error(f"Vehicle splitting failed: {e}")
            raise TMSException(e, sys)
                
    def _optimize_single_vehicle_route(self,orders: List[models.Order], vehicle: models.Vehicles):
        """Optimize vehicle with pre defined routes"""
        data = ORDataModel(db=self.db, vehicles=[vehicle], orders=orders).get_data()
        routes = VRPSolver().run_ortools_solver(data, [vehicle])
        if routes and 0 in routes and routes[0]["nodes"]:
            return {
                "vehicle": vehicle,
                "path": routes[0],
                "orders": orders
            }
            
    def _optimize_free_vehicles(self, orders: List[models.Order], vehicles: List[models.Vehicles]):
        """vrp for no routes assigned"""
        data = ORDataModel(db=self.db, vehicles=vehicles, orders=orders).get_data()
        routes = VRPSolver().run_ortools_solver(data=data, vehicles=vehicles)
        
        return [
            {
                "vehicle": vehicles[i],
			    "path": routes[i],  # Already contains nodes, arrival_times, total_distance, total_time
			    "orders": [o for o in orders if o.shop_id in routes[i]["nodes"]]
       }
            for i in range(len(routes)) if routes[i]["nodes"]
            ]
        
        
    def _save_job(self, db: Session, job: models.Job, routes_data: Dict):
        """Save routes into a Job with order tracking and proper timing."""       
        try:
            for route_idx, route_data in enumerate(routes_data):            
                # Get path data
                path = route_data.get("path", {})
                solver_nodes = path.get("nodes", [])
                orders_sequence = path.get("orders", [])
                arrival_times = path.get("arrival_times", [])
                departure_times = path.get("departure_times", [])
                total_distance=  path.get("total_distance", 0)
                total_time= path.get("total_time", 0)
                            
                # Create route record
                route = models.JobRoute(
                    job_id=job.id,
                    vehicle_id=route_data["vehicle"].id,
                    total_distance=total_distance,
                    total_time=total_time
                )
                db.add(route)
                db.flush()
                logging.info(f"Route {route.id} added to database for job {job.id}")

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

                    if departure_times and seq < len(departure_times):
                        minutes = int(departure_times[seq])
                        hours = minutes // 60
                        mins = minutes % 60
                        stop.departure_time = time(int(hours % 24), int(mins % 60))

                    db.add(stop)
                db.flush()
                logging.info(f"Added {len(solver_nodes)} stops to database for route {route.id}")

                # Generate and store Folium map
                try:
                    map_manager = MapManager(db)
                    map_html = map_manager.generate_map(solver_nodes)
                    if map_html:
                        route.folium_html = map_html
                        logging.info(f"Generated map for route {route.id}")
                    else:
                        logging.debug(f"Map generation returned None")
                        route.folium_html = None
                except Exception as e:
                    logging.error(f"Map generation error: {e}")
                    route.folium_html = None
            
            job.status = models.JobStatus.PLANNED
            db.commit()   
            db.refresh(job)
            logging.info(f"Changed job {job.id} status: 'planned'")
            return job
        except Exception as e:
            logging.error(f"Job saving to database failed: {e}")