"""TMS Backend entrypoint."""

import uvicorn

from src.api.app import app
from src.infrastructure import config

__all__ = ["app"]

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
    )
