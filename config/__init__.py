"""Project configuration package.

This module exposes a small set of top-level configuration values used by
modules that import `import config`.

For more structured settings use `config.settings.Settings`.
"""
from .settings import Settings

# Default solver time limit (seconds) used by OR-Tools if not overridden.
# You can set this via environment variables or extend Settings if you prefer.
SOLVER_TIME_LIMIT_SECONDS = 30

# Expose a default Settings instance for convenience
settings = Settings()

# Backwards-compat: keep names that older modules might expect
SettingsInstance = settings

