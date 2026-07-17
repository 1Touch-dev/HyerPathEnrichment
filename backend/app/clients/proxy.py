from __future__ import annotations

from urllib.parse import quote, urlsplit, urlunsplit

from app.core.config import get_settings


class ProxyProvider:
    """Resolves the outbound proxy every scraper should route through.

    ``PROXY_MODE=none`` (free default) returns ``None`` -> direct connection.
    ``scrapoxy``/``paid`` return the configured endpoint, with optional
    credentials folded into the URL. Turning proxies on later is a single env
    flip; no enricher changes.
    """

    def get(self) -> str | None:
        settings = get_settings()
        mode = settings.proxy_mode.strip().lower()
        if mode not in {"scrapoxy", "paid"}:
            return None

        endpoint = settings.scrapoxy_url.strip()
        if not endpoint:
            return None

        username = settings.scrapoxy_username.strip()
        password = settings.scrapoxy_password.strip()
        if not username:
            return endpoint

        parts = urlsplit(endpoint)
        host = parts.netloc.rsplit("@", 1)[-1]
        credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
        return urlunsplit((parts.scheme, f"{credentials}{host}", parts.path, parts.query, parts.fragment))
