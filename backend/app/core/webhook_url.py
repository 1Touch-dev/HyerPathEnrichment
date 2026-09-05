"""SSRF defenses for outbound webhook URLs (candidate + operator notify)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeWebhookUrlError(ValueError):
    """Raised when a webhook URL is missing, malformed, or resolves to a blocked target."""


def assert_safe_webhook_url(url: str) -> str:
    """Validate that ``url`` is a safe https webhook target.

    Rules:
    - Scheme must be ``https``
    - Host required; userinfo (credentials) rejected
    - Hostname must resolve to at least one address
    - All resolved addresses must be globally routable (no loopback / private /
      link-local / multicast / reserved / unspecified)

    Returns the stripped URL on success.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise UnsafeWebhookUrlError("webhook_url is required")

    parsed = urlparse(cleaned)
    if parsed.scheme != "https":
        raise UnsafeWebhookUrlError("webhook_url must use https")
    if not parsed.hostname:
        raise UnsafeWebhookUrlError("webhook_url must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeWebhookUrlError("webhook_url must not include credentials")

    hostname = parsed.hostname
    # Reject literal IPs that are not public before DNS.
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None and not _is_public_ip(literal):
        raise UnsafeWebhookUrlError("webhook_url must not target a private or local address")

    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeWebhookUrlError("webhook_url hostname could not be resolved") from exc

    if not addrinfo:
        raise UnsafeWebhookUrlError("webhook_url hostname could not be resolved")

    for entry in addrinfo:
        sockaddr = entry[4]
        ip = ipaddress.ip_address(sockaddr[0])
        if not _is_public_ip(ip):
            raise UnsafeWebhookUrlError(
                "webhook_url must not resolve to a private or local address"
            )

    return cleaned


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_global
        and not ip.is_loopback
        and not ip.is_private
        and not ip.is_link_local
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_unspecified
    )
