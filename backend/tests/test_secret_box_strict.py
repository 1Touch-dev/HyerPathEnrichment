"""Focused tests for strict Fernet secret decryption."""

from types import SimpleNamespace

import pytest
from cryptography.fernet import InvalidToken

from app.core import secret_box


def test_open_secret_strict_round_trip() -> None:
    plaintext = "short-sensitive-value"
    assert secret_box.open_secret_strict(secret_box.seal_secret(plaintext)) == plaintext


@pytest.mark.parametrize(
    "invalid",
    ["", "not-fernet-ciphertext", "plain-token-with-valid-looking-characters", "\N{LOCK}"],
)
def test_open_secret_strict_rejects_non_ciphertext(invalid: str) -> None:
    with pytest.raises(InvalidToken):
        secret_box.open_secret_strict(invalid)


def test_open_secret_strict_rejects_wrong_key(monkeypatch) -> None:
    sealed = secret_box.seal_secret("key-bound-secret")
    monkeypatch.setattr(
        secret_box,
        "get_settings",
        lambda: SimpleNamespace(SECRET_KEY="rotated-secret-key"),
    )
    with pytest.raises(InvalidToken):
        secret_box.open_secret_strict(sealed)


def test_legacy_open_secret_fallback_is_unchanged() -> None:
    plaintext = "legacy-plaintext"
    assert secret_box.open_secret(plaintext) == plaintext
