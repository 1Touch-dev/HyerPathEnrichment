from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import EnrichmentRequest


class Enricher(ABC):
    source_name: str

    async def initialize(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    @abstractmethod
    async def validate(self, request: EnrichmentRequest) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def run(self, request: EnrichmentRequest) -> dict[str, Any]:
        raise NotImplementedError

    async def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    async def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload
