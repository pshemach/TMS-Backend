import pandas as pd 
from config.settings import Settings


class MasterManager:
    def __init__(self, configs=None):
        self.gps_df = None
        
        self.config = configs
        if self.config is None:
            self.config = Settings()
        
    def load_gps(self):
        gps_csv_path = self.config.master_folder_path / self.config.gps_file_name
        df = pd.read_csv(gps_csv_path)
        return df