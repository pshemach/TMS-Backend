"""Project configuration package."""

from .settings import Settings

# Default solver time limit (seconds) used by OR-Tools if not overridden.
SOLVER_TIME_LIMIT_SECONDS = 30

# Expose a default Settings instance for convenience
settings = Settings()

# Backwards-compat: keep names that older modules might expect
SettingsInstance = settings

