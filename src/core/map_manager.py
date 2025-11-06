from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from src.database import models
from src.logger import logging
from src.exception import TMSException
import requests
import json
import ast
import sys
import folium
from folium import plugins


class MapManager:
    def __init__(self, db: Session):
        self.db = db
        
    def generate_map(self, shop_ids: List[int])-> Optional[str]:
        """Generate Folium map HTML for a route using cached paths from database."""
        try:
            if not shop_ids or len(shop_ids) < 2:
                logging.debug("No shops in solution route.")
                return None
            
            shops = self.db.query(models.GPSMaster).filter(
                models.GPSMaster.id.in_(shop_ids)
            ).all()
            
            if not shops:
                logging.debug("valid shops ids not found in solution route")
                return None
            
            shop_by_id = {s.id: s for s in shops}
            
                        # Get all shop coordinates
            shop_coords = []
            for sid in shop_ids:
                s = shop_by_id.get(sid)
                if s:
                    shop_coords.append((s.latitude, s.longitude))
                else:
                    logging.debug(f"Warning: Shop {sid} not found in fetched shops")
            
            if not shop_coords:
                logging.debug("No valid shop coordinates found")
                return None
            
            # Center map
            avg_lat = sum(lat for lat, _ in shop_coords) / len(shop_coords)
            avg_lon = sum(lon for _, lon in shop_coords) / len(shop_coords)
            
            fmap = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, tiles="OpenStreetMap")

            all_path_coords = []
            for i in range(len(shop_ids) - 1):
                origin_id = shop_ids[i]
                dest_id = shop_ids[i + 1]
                
                origin_shop = shop_by_id.get(origin_id)
                dest_shop = shop_by_id.get(dest_id)
                
                if not origin_shop or not dest_shop:
                    logging.debug(f"Skipping segment {origin_id} -> {dest_id}: shop not found")
                    continue
                if origin_shop == dest_shop:
                    continue
                
                path_coords = self._get_path_coordinates(
                    origin_id=origin_id,
                    dest_id=dest_id,
                    origin_coords=(origin_shop.latitude, origin_shop.longitude),
                    dest_coords=(dest_shop.latitude, dest_shop.longitude)
                )
                
                if path_coords:
                    if len(path_coords) > 2:
                        all_path_coords.append(path_coords)
                    else:
                        logging.debug(f"✗ Path too short ({len(path_coords)} points)")
                else:
                    logging.debug(f"✗ No path returned for {origin_id} -> {dest_id}")
                  
            html_string = self._get_map_html(fmap=fmap, all_path_coords=all_path_coords, shop_coords=shop_coords, shop_ids=shop_ids, shop_by_id=shop_by_id)
            return html_string
        except Exception as e:
            logging.error(f"ERROR in map generation: {e}")
            return None
        
    def _get_map_html(self, fmap, all_path_coords, shop_coords, shop_ids, shop_by_id):
        """Generate map html"""
        if all_path_coords:
            for idx, segment in enumerate(all_path_coords):
                try:
                    # Draw solid route line
                    folium.PolyLine(
                            locations=segment,
                            color="#5EFF66",
                            weight=6,
                            opacity=0.8,
                            popup=f"Segment {idx + 1}"
                        ).add_to(fmap)
                    # Add animated ant path overlay
                    plugins.AntPath(
                            locations=segment,
                            color="#FF6B6B", 
                            weight=2,
                            opacity=0.6,
                            delay=500,  # Animation speed (ms)
                            dash_array=[10, 20], 
                            pulse_color="#FFFFFF"  
                        ).add_to(fmap)
                except Exception as e:
                    logging.error(f"  ✗ Error drawing segment {idx}: {e}")
                    
        else:
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
        for seq, sid in enumerate(shop_ids):
            s = shop_by_id.get(sid)
            if not s:
                continue
            
            is_depot = (seq == 0) or (seq == len(shop_ids) - 1)
            
            try:
                if is_depot:
                    # Depot marker (green with home icon)
                    folium.Marker(
                            location=[s.latitude, s.longitude],
                            popup=f"🏠 DEPOT<br>{getattr(s, 'shop_code', '')}<br>{getattr(s, 'location', '')}",
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
                            popup=f"Stop {seq}<br>{getattr(s, 'shop_code', '')}<br>{getattr(s, 'location', '')}<br>{getattr(s, 'brand', '')}",
                            tooltip=f"Stop {seq}",
                            icon=folium.DivIcon(html=icon_html)
                        ).add_to(fmap)
                    
            except Exception as e:
                logging.error(f"Error adding marker {seq}: {e}")
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
        
        html_string = fmap.get_root().render()
        
        return html_string
                
                
    def _get_path_coordinates(self,origin_id: int, dest_id: int, origin_coords: Tuple[float, float], dest_coords: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
        """
        Get path coordinates between two shops.
        First tries database cache, then falls back to OSRM API.
        """
        # Try to get from database cache (bidirectional)
        matrix_entry = self.db.query(models.MatrixMaster).filter(
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
            path_coords = self._get_osrm_route(origin_coords, dest_coords)
            
            # Cache the result in database for future use
            if path_coords:
                logging.info(f"Got {len(path_coords)} points from OSRM, caching...")
                self._cache_path_in_db(origin_id, dest_id, path_coords)
            else:
                logging.debug(f"OSRM returned no path for {origin_id} -> {dest_id}")
            
            return path_coords
        except Exception as e:
            logging.error(f"Error fetching OSRM route: {e}")
            return None
            
        
    def _cache_path_in_db(self, origin_id: int, dest_id: int, path_coords: List[Tuple[float, float]]):
        """Cache path coordinates in database."""
        try:
            # Check if already exists
            existing = self.db.query(models.MatrixMaster).filter(
                ((models.MatrixMaster.shop_id_1 == origin_id) & (models.MatrixMaster.shop_id_2 == dest_id)) |
                ((models.MatrixMaster.shop_id_1 == dest_id) & (models.MatrixMaster.shop_id_2 == origin_id))
            ).first()
            
            # Convert coords to list format for JSON storage
            coords_json = [[lat, lon] for lat, lon in path_coords]
            
            if existing:
                if not existing.coords or (isinstance(existing.coords, str) and existing.coords == 'null'):
                    # Update existing entry with coords
                    existing.coords = coords_json
                    self.db.commit()
                    logging.info(f"Updated cache with {len(path_coords)} points for {origin_id} -> {dest_id}")
                else:
                    logging.debug(f"Cache already exists for {origin_id} -> {dest_id}, skipping update")
            else:
                logging.debug(f"Warning: No MatrixMaster entry found for {origin_id} -> {dest_id}, cannot cache coords")
                
        except Exception as e:
            logging.error(f"Warning: Failed to cache path in database: {e}")
            self.db.rollback()
            
    def _get_osrm_route(self, origin: Tuple[float, float],destination: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
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
