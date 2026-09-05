"""P2 security hardenings: CLI sanitize, magic sniff, metrics auth, LinkedIn URL."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.clients.cli_args import sanitize_cli_arg
from app.core.file_sniff import claimed_mime_matches_bytes, sniff_document_mime
from app.main import app
from app.modules.linkedin_sourcing.service import _normalize_profile_url


def test_sanitize_cli_arg_rejects_leading_dash() -> None:
    with pytest.raises(ValueError, match="must not start"):
        sanitize_cli_arg("-o", label="username")


def test_sanitize_cli_arg_rejects_nul() -> None:
    with pytest.raises(ValueError, match="NUL"):
        sanitize_cli_arg("user\x00name", label="username")


def test_sanitize_cli_arg_accepts_normal() -> None:
    assert sanitize_cli_arg("  alice  ") == "alice"


def test_sniff_pdf_magic() -> None:
    assert sniff_document_mime(b"%PDF-1.7\n%") == "application/pdf"


def test_claimed_mime_mismatch_rejected() -> None:
    # HTML pretending to be PDF
    assert claimed_mime_matches_bytes("application/pdf", b"<html>not pdf</html>") is False


def test_claimed_mime_pdf_ok() -> None:
    assert claimed_mime_matches_bytes("application/pdf", b"%PDF-1.4\n") is True


def test_normalize_linkedin_profile_url() -> None:
    assert (
        _normalize_profile_url("https://www.linkedin.com/in/Jane-Doe/")
        == "https://www.linkedin.com/in/jane-doe"
    )


def test_normalize_linkedin_rejects_company_url() -> None:
    with pytest.raises(HTTPException) as exc:
        _normalize_profile_url("https://www.linkedin.com/company/acme")
    assert exc.value.status_code == 422


def test_metrics_open_in_development_without_metrics_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("METRICS_TOKEN", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    get_settings.cache_clear()


def test_metrics_requires_token_when_metrics_token_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("METRICS_TOKEN", "scrape-secret")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    denied = client.get("/metrics")
    assert denied.status_code == 401
    ok = client.get("/metrics", headers={"X-API-Token": "scrape-secret"})
    assert ok.status_code == 200
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_sherlock_skips_leading_dash_username() -> None:
    from app.domain.enrichment import EnrichmentRequest
    from app.enrichers.sherlock import SherlockEnricher

    enricher = SherlockEnricher()
    request = EnrichmentRequest.model_construct(username="-evil")
    with patch("app.enrichers.sherlock.run_command", new_callable=AsyncMock) as mock_run:
        result = await enricher._fetch(request)
        assert result == {}
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_upload_rejects_mime_magic_mismatch() -> None:
    from app.modules.documents.service import DocumentService

    service = DocumentService(db=MagicMock(), redis_conn=MagicMock())
    upload = MagicMock()
    upload.content_type = "application/pdf"
    upload.read = AsyncMock(return_value=b"<html>spoof</html>")
    upload.filename = "cv.pdf"

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(upload, uuid4())
    assert exc.value.status_code == 400
    assert "Content-Type" in str(exc.value.detail)
