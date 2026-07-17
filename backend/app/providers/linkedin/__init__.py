"""Compatibility shim — prefer app.integrations.linkedin."""
from app.integrations.linkedin import *  # noqa: F403
from app.integrations import linkedin as _m
__all__ = list(getattr(_m, "__all__", []))

def __getattr__(name):
    return getattr(_m, name)
