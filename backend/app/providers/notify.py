"""Compatibility shim — prefer app.clients.notify."""

from app.clients.notify import *  # noqa: F401,F403
from app.clients import notify as _m

globals().update({name: getattr(_m, name) for name in dir(_m) if not name.startswith("__")})
__all__ = [n for n in dir(_m) if not n.startswith("_")]
