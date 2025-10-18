import requests
import numpy as np


def get_osrm_data(origin, destination):
    """
    Get the distance and path between two coordinates using OSRM API.
    :param origin: (latitude, longitude)
    :param destination: (latitude, longitude)
    :return: Tuple of (path_coordinates, distance in km, duration in minutes)
    """
    osrm_base_url = "http://router.project-osrm.org/route/v1/car"
    url = f"{osrm_base_url}/{origin[1]},{origin[0]};{destination[1]},{destination[0]}?overview=full&geometries=geojson"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if "routes" in data and len(data["routes"]) > 0:
            path_cords = data["routes"][0]["geometry"]["coordinates"]
            # Convert [longitude, latitude] to [latitude, longitude] for folium
            path_cords = [[coord[1], coord[0]] for coord in path_cords]
            distance = data["routes"][0]["distance"] / 1000
            duration = data["routes"][0]["duration"] / 60
            return path_cords, distance, duration

    return None, None, None