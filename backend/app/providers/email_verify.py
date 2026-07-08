from __future__ import annotations

import logging
import re
from typing import Any

from app.config import get_settings
from app.providers.sidecar import SidecarClient

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailVerifier:
    """Ordered email-verification fallback chain behind one call.

    ``EMAIL_VERIFY_LEVEL=basic`` (free default): syntax + MX, plus the AfterShip
    email-verifier sidecar when reachable. ``smtp`` adds the Reacher SMTP check
    (needs port 25 + a clean IP). Every path returns the same ``VerifiedEmail``
    shape (``value``, ``status``, ``confidence``, ``source``) or ``None`` when
    the address is unusable, so callers stay identical across free/paid.
    """

    async def verify(self, email: str) -> dict[str, Any] | None:
        email = (email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            return None

        settings = get_settings()
        result: dict[str, Any] = {
            "value": email,
            "status": "unknown",
            "confidence": 0.3,
            "source": "syntax",
        }

        mx_ok = await self._mx_ok(email.rsplit("@", 1)[-1])
        if mx_ok is True:
            result.update(status="deliverable", confidence=0.55, source="mx")
        elif mx_ok is False:
            result.update(status="undeliverable", confidence=0.1, source="mx")

        aftership = await self._aftership(settings.email_verifier_url, email)
        if aftership is not None:
            result.update(aftership)

        if settings.email_verify_level.strip().lower() == "smtp":
            reacher = await self._reacher(settings.reacher_url, email)
            if reacher is not None:
                result.update(reacher)

        return result

    async def _mx_ok(self, domain: str) -> bool | None:
        try:
            import dns.resolver
            from dns.resolver import NXDOMAIN, NoAnswer, NoNameservers
        except ImportError:
            return None
        try:
            answers = dns.resolver.resolve(domain, "MX")
            return len(answers) > 0
        except (NXDOMAIN, NoAnswer, NoNameservers):
            # Domain resolves but has no mail exchanger -> definitively undeliverable.
            return False
        except Exception:
            # Timeout / transient resolver error -> unknown, not a verdict.
            return None

    async def _aftership(self, url: str, email: str) -> dict[str, Any] | None:
        client = SidecarClient(url)
        data = await client.get_json(f"/v1/{email}/verification")
        if not isinstance(data, dict):
            return None
        reachable = bool(data.get("reachable") not in (None, "", "unknown")) and bool(
            data.get("has_mx_records", True)
        )
        return {
            "status": "deliverable" if reachable else "risky",
            "confidence": 0.8 if reachable else 0.4,
            "source": "AfterShip Email Verifier",
        }

    async def _reacher(self, url: str, email: str) -> dict[str, Any] | None:
        settings = get_settings()
        client = SidecarClient(url)
        payload: dict[str, Any] = {"to_email": email}
        if settings.reacher_from_email.strip():
            payload["from_email"] = settings.reacher_from_email.strip()
        data = await client.post_json("/v1/check_email", json=payload)
        if not isinstance(data, dict):
            return None
        reachability = str(data.get("is_reachable", "unknown")).lower()
        confidence = {"safe": 0.95, "risky": 0.5, "invalid": 0.05, "unknown": 0.3}.get(
            reachability, 0.3
        )
        status = {
            "safe": "verified",
            "risky": "risky",
            "invalid": "undeliverable",
            "unknown": "unknown",
        }.get(reachability, "unknown")
        return {"status": status, "confidence": confidence, "source": "Reacher"}
