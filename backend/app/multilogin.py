"""Backward-compatible re-exports for the Multilogin provider layer."""

from app.providers.multilogin import (
    MultiloginClient,
    MultiloginError,
    get_token,
    list_profiles,
    sign_in,
    start_profile,
    stop_profile,
)

__all__ = [
    "MultiloginClient",
    "MultiloginError",
    "get_token",
    "list_profiles",
    "sign_in",
    "start_profile",
    "stop_profile",
]
