"""Config-selected backends that hide the free-vs-paid choice.

These providers are the only place that knows whether the system is running in
free/self-hosted mode or against a paid backend. Enrichers depend on the
providers, never on the concrete backend, so a free -> paid switch is an env
var flip (see ``config.py`` mode flags) with no enricher edits.
"""

from app.providers.browser import BrowserProvider
from app.providers.email_verify import EmailVerifier
from app.providers.process import run_command
from app.providers.proxy import ProxyProvider
from app.providers.sidecar import SidecarClient

__all__ = [
    "BrowserProvider",
    "EmailVerifier",
    "ProxyProvider",
    "SidecarClient",
    "run_command",
]
