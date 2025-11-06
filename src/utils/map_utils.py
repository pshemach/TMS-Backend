from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from src.database import models
import requests
import json
import ast
import sys
from src.logger import logging
from src.exception import TMSException


def generate_map(db: Session, shop_ids: List[int])-> Optional[str]:
        """Generate Folium map HTML for a route using cached paths from database."""
        try:
            if not shop_ids or len(shop_ids) < 2:
                logging.debug("No shops in solution route.")
                return None
            
            shops = db.query(models.GPSMaster).filter(
                models.OrderGroup.id.in_(shop_ids)
            ).all()
            
            if not shops:
                logging.debug("valid shops ids not found in solution route")
                return None
            
        except Exception as e:
            logging.error(f"ERROR in map generation: {e}")
            return None

def get_path_coordinates(
    db: Session,
    origin_id: int,
    dest_id: int,
    origin_coords: Tuple[float, float],
    dest_coords: Tuple[float, float]
) -> Optional[List[Tuple[float, float]]]:
    """
    Get path coordinates between two shops.
    First tries database cache, then falls back to OSRM API.
    """
    # Try to get from database cache (bidirectional)
    matrix_entry = db.query(models.MatrixMaster).filter(
        ((models.MatrixMaster.shop_id_1 == origin_id) & (models.MatrixMaster.shop_id_2 == dest_id)) |
        ((models.MatrixMaster.shop_id_1 == dest_id) & (models.MatrixMaster.shop_id_2 == origin_id))
    ).first()
    
    if matrix_entry and matrix_entry.coords:
        try:
            # Handle different storage formats
            coords = matrix_entry.coords
            
            # If coords is a string, parse it
            if isinstance(coords, str):
                # Try JSON parsing first
                try:
                    coords = json.loads(coords)
                except json.JSONDecodeError:
                    # Fall back to ast.literal_eval for Python literals
                    try:
                        coords = ast.literal_eval(coords)
                    except (ValueError, SyntaxError) as e:
                        logging.error(f"Failed to parse coords string: {e}")
                        coords = None
            
            if coords:
                # Handle potential reverse direction
                if matrix_entry.shop_id_1 == dest_id and matrix_entry.shop_id_2 == origin_id:
                    coords = list(reversed(coords))
                
                # Convert to tuple format - handle both [lat, lon] and (lat, lon)
                path_coords = []
                for c in coords:
                    if isinstance(c, (list, tuple)) and len(c) >= 2:
                        path_coords.append((float(c[0]), float(c[1])))
                        
                return path_coords
            
        except Exception as e:
            logging.error(f"Error parsing cached coords: {e}")
    
    # Fall back to OSRM API
    logging.info(f"No valid cache found, fetching path from OSRM for {origin_id} -> {dest_id}")
    try:
        path_coords = get_osrm_route(origin_coords, dest_coords)
        
        # Cache the result in database for future use
        if path_coords:
            logging.info(f"Got {len(path_coords)} points from OSRM, caching...")
            cache_path_in_db(db, origin_id, dest_id, path_coords)
        else:
            logging.debug(f"OSRM returned no path for {origin_id} -> {dest_id}")
        
        return path_coords
    except Exception as e:
        logging.error(f"Error fetching OSRM route: {e}")
        return None


def get_osrm_route(
    origin: Tuple[float, float],
    destination: Tuple[float, float]
) -> Optional[List[Tuple[float, float]]]:
    """Get route from OSRM API."""
    # OSRM expects longitude,latitude format
    url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    params = {
        'overview': 'full',
        'geometries': 'geojson'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 'Ok' and data.get('routes'):
            coordinates = data['routes'][0]['geometry']['coordinates']
            # Convert from [lon, lat] to (lat, lon)
            path_coords = [(coord[1], coord[0]) for coord in coordinates]
            logging.info(f"OSRM returned {len(path_coords)} coordinates")
            return path_coords
        else:
            logging.debug(f"OSRM response code: {data.get('code')}, routes: {bool(data.get('routes'))}")
        
        return None
    except Exception as e:
        logging.error(f"OSRM API error: {e}")
        return None


def cache_path_in_db(
    db: Session,
    origin_id: int,
    dest_id: int,
    path_coords: List[Tuple[float, float]]
):
    """Cache path coordinates in database."""
    try:
        # Check if already exists
        existing = db.query(models.MatrixMaster).filter(
            ((models.MatrixMaster.shop_id_1 == origin_id) & (models.MatrixMaster.shop_id_2 == dest_id)) |
            ((models.MatrixMaster.shop_id_1 == dest_id) & (models.MatrixMaster.shop_id_2 == origin_id))
        ).first()
        
        # Convert coords to list format for JSON storage
        coords_json = [[lat, lon] for lat, lon in path_coords]
        
        if existing:
            if not existing.coords or (isinstance(existing.coords, str) and existing.coords == 'null'):
                # Update existing entry with coords
                existing.coords = coords_json
                db.commit()
                logging.info(f"Updated cache with {len(path_coords)} points for {origin_id} -> {dest_id}")
            else:
                logging.debug(f"Cache already exists for {origin_id} -> {dest_id}, skipping update")
        else:
            logging.debug(f"Warning: No MatrixMaster entry found for {origin_id} -> {dest_id}, cannot cache coords")
            
    except Exception as e:
        logging.error(f"Warning: Failed to cache path in database: {e}")
        db.rollback()