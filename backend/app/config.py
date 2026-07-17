"""Compatibility shim — prefer app.core.config."""
from app.core.config import *  # noqa: F403
from app.core.config import Settings, get_settings, validate_tier1_settings
__all__ = ["Settings", "get_settings", "validate_tier1_settings"]
