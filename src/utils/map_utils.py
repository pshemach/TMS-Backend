from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from src.database import models
import requests
import json
import ast

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
    
    Args:
        db: Database session
        origin_id: Origin shop ID
        dest_id: Destination shop ID
        origin_coords: Origin (latitude, longitude)
        dest_coords: Destination (latitude, longitude)
    
    Returns:
        List of coordinate tuples [(lat, lon), ...] or None if failed
    """
    # Try to get from database cache (bidirectional)
    matrix_entry = db.query(models.MatrixMaster).filter(
        ((models.MatrixMaster.shop_id_1 == origin_id) & (models.MatrixMaster.shop_id_2 == dest_id)) |
        ((models.MatrixMaster.shop_id_1 == dest_id) & (models.MatrixMaster.shop_id_2 == origin_id))
    ).first()
    
    if matrix_entry and matrix_entry.coords:
        print(f"Using cached path for {origin_id} -> {dest_id}")
        
        try:
            # Handle different storage formats
            coords = matrix_entry.coords
            
            # If coords is a string, parse it
            if isinstance(coords, str):
                print(f"Parsing string-stored coords...")
                # Try JSON parsing first
                try:
                    coords = json.loads(coords)
                except json.JSONDecodeError:
                    # Fall back to ast.literal_eval for Python literals
                    try:
                        coords = ast.literal_eval(coords)
                    except (ValueError, SyntaxError) as e:
                        print(f"Failed to parse coords string: {e}")
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
                
                print(f"Successfully parsed {len(path_coords)} cached coordinates")
                return path_coords
            
        except Exception as e:
            print(f"Error parsing cached coords: {e}")
            # Fall through to OSRM
    
    # Fall back to OSRM API
    print(f"No valid cache found, fetching path from OSRM for {origin_id} -> {dest_id}")
    try:
        path_coords = get_osrm_route(origin_coords, dest_coords)
        
        # Cache the result in database for future use
        if path_coords:
            print(f"Got {len(path_coords)} points from OSRM, caching...")
            _cache_path_in_db(db, origin_id, dest_id, path_coords)
        else:
            print(f"OSRM returned no path for {origin_id} -> {dest_id}")
        
        return path_coords
    except Exception as e:
        print(f"Error fetching OSRM route: {e}")
        return None


def get_osrm_route(
    origin: Tuple[float, float],
    destination: Tuple[float, float]
) -> Optional[List[Tuple[float, float]]]:
    """
    Get route from OSRM API.
    
    Args:
        origin: Origin (latitude, longitude)
        destination: Destination (latitude, longitude)
    
    Returns:
        List of coordinate tuples [(lat, lon), ...] or None if failed
    """
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
            print(f"OSRM returned {len(path_coords)} coordinates")
            return path_coords
        else:
            print(f"OSRM response code: {data.get('code')}, routes: {bool(data.get('routes'))}")
        
        return None
    except Exception as e:
        print(f"OSRM API error: {e}")
        return None


def _cache_path_in_db(
    db: Session,
    origin_id: int,
    dest_id: int,
    path_coords: List[Tuple[float, float]]
):
    """
    Cache path coordinates in database.
    Updates existing MatrixMaster entry with proper JSON format.
    """
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
                print(f"Updated cache with {len(path_coords)} points for {origin_id} -> {dest_id}")
            else:
                print(f"Cache already exists for {origin_id} -> {dest_id}, skipping update")
        else:
            print(f"Warning: No MatrixMaster entry found for {origin_id} -> {dest_id}, cannot cache coords")
            
    except Exception as e:
        print(f"Warning: Failed to cache path in database: {e}")
        db.rollback()