"""Shared application logging setup."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from from_root import from_root

from src.infrastructure.config import ensure_directories

ensure_directories()

LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
logs_path = os.path.join(from_root(), "logs", LOG_FILE)

logging.basicConfig(
    filename=logs_path,
    format="[ %(asctime)s ] %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)

__all__ = ["logging"]
