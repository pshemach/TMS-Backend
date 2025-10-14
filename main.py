# from src.logger import logging
from src.exception import TMSException
import sys
from config.settings import Settings


def main():
    try:
        settings = Settings()
        
        print(settings.project_root_path)
        print(settings.client_data_name)
        
        
    except Exception as e:
        raise TMSException(e, sys)

if __name__ == "__main__":
    main()
