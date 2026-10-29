"""OSRM HTTP client for distance, duration, and path geometry."""

from __future__ import annotations

import requests

from src.infrastructure.config import OSRM_BASE_URL


def get_osrm_data(origin, destination):
    """
    Get the distance and path between two coordinates using OSRM API.
    :param origin: (latitude, longitude)
    :param destination: (latitude, longitude)
    :return: Tuple of (path_coordinates, distance in km, duration in minutes)
    """
    url = (
        f"{OSRM_BASE_URL}/{origin[1]},{origin[0]};"
        f"{destination[1]},{destination[0]}?overview=full&geometries=geojson"
    )
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if "routes" in data and len(data["routes"]) > 0:
            path_cords = data["routes"][0]["geometry"]["coordinates"]
            path_cords = [[coord[1], coord[0]] for coord in path_cords]
            distance = data["routes"][0]["distance"] / 1000
            duration = data["routes"][0]["duration"] / 60
            return path_cords, distance, duration
    return None, None, None
