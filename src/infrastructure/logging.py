"""Shared Loguru logging — console + rotating file, LOG_LEVEL from env.

Usage (existing call sites keep working):
    from src.infrastructure.logging import logging
    logging.info("...")

Or the Loguru-native name:
    from src.infrastructure.logging import logger
    logger.info("...")

Debug when needed:
    LOG_LEVEL=DEBUG   # .env or shell — not the default in production
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from datetime import datetime

from from_root import from_root
from loguru import logger

from src.infrastructure.config import LOG_DIR, LOG_LEVEL, ensure_directories

ensure_directories()

LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
logs_path = LOG_DIR / LOG_FILE

# Drop Loguru's default stderr sink, then add ours.
logger.remove()

_LEVEL = LOG_LEVEL if LOG_LEVEL in {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"} else "INFO"

# Console — human-readable while developing / watching the terminal
logger.add(
    sys.stderr,
    level=_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>",
    enqueue=True,
    backtrace=True,
    diagnose=_LEVEL == "DEBUG",
)

# File — one file per process start; keep history without filling disk
logger.add(
    str(logs_path),
    level=_LEVEL,
    format="[{time:YYYY-MM-DD HH:mm:ss.SSS}] {level} | {name}:{function}:{line} - {message}",
    rotation="50 MB",
    retention="14 days",
    enqueue=True,
    backtrace=True,
    diagnose=_LEVEL == "DEBUG",
)


class InterceptHandler(stdlib_logging.Handler):
    """Route stdlib logging (uvicorn, sqlalchemy, ortools, …) into Loguru."""

    def emit(self, record: stdlib_logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == stdlib_logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _intercept_stdlib() -> None:
    stdlib_logging.root.handlers = [InterceptHandler()]
    stdlib_logging.root.setLevel(stdlib_logging.NOTSET)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "ortools"):
        lib = stdlib_logging.getLogger(name)
        lib.handlers = [InterceptHandler()]
        lib.propagate = False


_intercept_stdlib()

# Back-compat alias so existing `from src.infrastructure.logging import logging` still works.
logging = logger

__all__ = ["logger", "logging", "logs_path"]
