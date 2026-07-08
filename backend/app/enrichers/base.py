from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.models import EnrichmentRequest

logger = logging.getLogger(__name__)


class Enricher(ABC):
    source_name: str

    async def initialize(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    @abstractmethod
    async def validate(self, request: EnrichmentRequest) -> bool:
        raise NotImplementedError

    async def run(self, request: EnrichmentRequest) -> dict[str, Any]:
        """Template method: call the backend, degrade to an empty fragment.

        A missing tool, unreachable sidecar, or unset key must never crash the
        pipeline (``_dispatch`` isolates failures, but enrichers own graceful
        degradation too). Subclasses implement ``_fetch`` and return a partial
        dossier dict; this wrapper tags the source and swallows failures.
        """
        try:
            fragment = await self._fetch(request)
        except Exception:
            logger.warning("enricher %s failed", self.source_name, exc_info=True)
            return {}
        if not fragment:
            return {}
        fragment.setdefault("sources", [self.source_name])
        return fragment

    @abstractmethod
    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        raise NotImplementedError

    async def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    async def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload
