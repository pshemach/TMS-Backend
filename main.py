from src.logger import logging
from src.exception import TMSException
import sys

def main():
    try:
        logging.info("Hello from tms-backend!")
        
    except Exception as e:
        logging.error(f"Error occurred {e}")
        raise TMSException(e, sys)

if __name__ == "__main__":
    main()
