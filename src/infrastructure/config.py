"""
Application configuration — module-level constants.

CONFIGURATION POLICY:
====================
Non-secret defaults and paths are defined here (or via env vars).
Secrets (database URL, API keys) live ONLY in .env and are loaded via os.getenv().
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ========================================
# Bootstrap
# ========================================

# Project root: parent of src/infrastructure/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# ========================================
# Client / data paths
# ========================================

CLIENT = os.getenv("CLIENT", "common")
DATA_FOLDER = os.getenv("DATA_FOLDER", "data")
MASTER_FOLDER = os.getenv("MASTER_FOLDER", "master")
GPS_FILE_NAME = os.getenv("MASTER_GPS", "master_gps.csv")
DISTANCE_MATRIX_FILE_NAME = os.getenv("DISTANCE_MATRIX", "distance_matrix.csv")
DURATION_MATRIX_FILE_NAME = os.getenv("DURATION_MATRIX", "duration_matrix.csv")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "outputs")
DATABASE_FOLDER = os.getenv("DATABASE_FOLDER", "database")

DATA_DIR = PROJECT_ROOT / DATA_FOLDER
CLIENT_DATA_DIR = DATA_DIR / CLIENT
MASTER_DIR = CLIENT_DATA_DIR / MASTER_FOLDER
OUTPUTS_DIR = CLIENT_DATA_DIR / OUTPUT_FOLDER
DATABASE_DIR = OUTPUTS_DIR / DATABASE_FOLDER

DISTANCE_MATRIX_PATH = MASTER_DIR / DISTANCE_MATRIX_FILE_NAME
DURATION_MATRIX_PATH = MASTER_DIR / DURATION_MATRIX_FILE_NAME
GPS_FILE_PATH = MASTER_DIR / GPS_FILE_NAME

# ========================================
# Database
# ========================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DATABASE_DIR / (CLIENT + '.db')}",
)

# ========================================
# Solver
# ========================================

SOLVER_TIME_LIMIT_SECONDS = int(os.getenv("SOLVER_TIME_LIMIT_SECONDS", "30"))

# ========================================
# OSRM
# ========================================

OSRM_BASE_URL = os.getenv(
    "OSRM_BASE_URL",
    "http://router.project-osrm.org/route/v1/car",
)

# ========================================
# Logging
# ========================================

LOG_DIR = PROJECT_ROOT / "logs"
UI_DIR = PROJECT_ROOT / "ui"


def ensure_directories() -> None:
    """Create required data / log directories if missing."""
    for path in (DATA_DIR, CLIENT_DATA_DIR, MASTER_DIR, OUTPUTS_DIR, DATABASE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def validate() -> None:
    """Validate required configuration and ensure directories exist."""
    if not DATABASE_URL:
        raise ValueError(
            "Missing required secret: DATABASE_URL\n"
            "Please add it to your .env file."
        )
    ensure_directories()
