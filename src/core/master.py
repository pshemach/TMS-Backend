import pandas as pd 
from config.settings import Settings

class MasterManager:
    def __init__(self, configs):
        self.gps_df = None
        self.distance_matrix_df = None
        self.duration_matrix_df = None
        
    def load_gps(self):
        pass