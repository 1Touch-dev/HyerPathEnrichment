"""Compatibility shim — prefer app.integrations.linkedin.browser_facade."""

from app.integrations.linkedin.browser_facade import *  # noqa: F401,F403
from app.integrations.linkedin import browser_facade as _facade

# Re-export everything the facade exposes, including test helpers.
globals().update({name: getattr(_facade, name) for name in dir(_facade) if not name.startswith("__")})
__all__ = list(getattr(_facade, "__all__", []))
