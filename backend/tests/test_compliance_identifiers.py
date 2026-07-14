"""Tests for canonical identifier normalization."""

from app.compliance.identifiers import hash_identifier, normalize_identifier


def test_email_normalization_is_lowercase() -> None:
    assert normalize_identifier("Jane@Example.COM") == "jane@example.com"


def test_linkedin_url_variants_hash_identically() -> None:
    urls = [
        "https://www.linkedin.com/in/jane-doe",
        "linkedin.com/in/jane-doe/",
        "https://linkedin.com/in/jane-doe",
    ]
    hashes = {hash_identifier(url) for url in urls}
    assert len(hashes) == 1
    assert normalize_identifier(urls[0]) == "linkedin:jane-doe"


def test_username_normalization() -> None:
    assert normalize_identifier("  JaneDoe  ") == "janedoe"
