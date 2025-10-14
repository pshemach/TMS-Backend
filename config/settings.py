from dotenv import load_dotenv
import os 
from pathlib import Path

load_dotenv()

class Settings:
    def __init__(self):
        # data folder 
        self.project_root_path = Path(__file__).parent.parent
        self.data_folder_name = os.getenv("DATA_FOLDER", 'data')
        self.client_data_name = os.getenv('CLIENT', 'common')
        
        # master gps and matrixes file details 
        self.master_folder_name = os.getenv('MASTER_FOLDER', 'master')
        self.gps_file_name = os.getenv('MASTER_GPS', 'master_gps.csv')
        self.distance_matrix_file_name = os.getenv('DISTANCE_MATRIX', 'distance_matrix.csv')
        self.duration_matrix_file_name = os.getenv('DURATION_MATRIX', 'duration_matrix.csv')
        
        self.data_folder_path = self.project_root_path / self.data_folder_name
        self.client_data_path = self.data_folder_path / self.client_data_name
        self.master_folder_path = self.client_data_path / self.master_folder_name
        
        self.data_folder_path.mkdir(parents=True, exist_ok=True)
        self.client_data_path.mkdir(parents=True, exist_ok=True)
        self.master_folder_path.mkdir(parents=True, exist_ok=True)