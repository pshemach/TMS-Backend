import pandas as pd 
from src.database.database import engine
from config.settings import Settings


class MasterManager:
    def __init__(self, configs=None):
        self.config = configs
        if self.config is None:
            self.config = Settings()
            
        self.gps_df = self._load_gps()
    def _load_gps(self):
        df = pd.read_sql("SELECT * FROM master_gps", engine)
        gps_csv_path = self.config.master_folder_path / self.config.gps_file_name
        df.to_csv(gps_csv_path, index=False)
        return df
    
    def update_matrix(self):
        pass