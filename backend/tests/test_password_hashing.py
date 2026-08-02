"""Password hashing and security tests."""

from __future__ import annotations

import time

import pytest

from app.auth.password import (
    generate_secure_token,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_hash_password_generates_different_hashes() -> None:
    """Test that same password generates different hashes (due to salt)."""
    password = "SecurePassword123!"

    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Different hashes due to random salt
    assert hash1 != hash2

    # Both should start with bcrypt identifier
    assert hash1.startswith("$2b$")
    assert hash2.startswith("$2b$")


def test_verify_password_correct() -> None:
    """Test password verification with correct password."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect() -> None:
    """Test password verification with incorrect password."""
    password = "MySecurePassword123!"
    wrong_password = "WrongPassword456!"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_verify_password_case_sensitive() -> None:
    """Test password verification is case-sensitive."""
    password = "Password123"
    hashed = hash_password(password)

    assert verify_password("password123", hashed) is False
    assert verify_password("PASSWORD123", hashed) is False


def test_verify_password_special_characters() -> None:
    """Test password with special characters."""
    password = "P@ssw0rd!#$%^&*()"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_unicode() -> None:
    """Test password with unicode characters."""
    password = "Pässwörd123日本語"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_empty_string() -> None:
    """Test empty password handling."""
    # Empty passwords should still hash
    password = ""
    hashed = hash_password(password)

    assert verify_password("", hashed) is True
    assert verify_password("notempty", hashed) is False


def test_hash_password_uses_bcrypt_rounds_12() -> None:
    """Test password hashing uses 12 rounds (2^12 iterations)."""
    password = "TestPassword123"
    hashed = hash_password(password)

    # Bcrypt format: $2b$12$... where 12 is the cost factor
    parts = hashed.split("$")
    assert len(parts) >= 4
    assert parts[2] == "12"


def test_verify_password_timing_attack_resistance() -> None:
    """Test verification has constant-time comparison (timing attack resistance)."""
    password = "CorrectPassword123"
    hashed = hash_password(password)

    # Measure time for correct password
    iterations = 10
    start = time.perf_counter()
    for _ in range(iterations):
        verify_password(password, hashed)
    correct_time = (time.perf_counter() - start) / iterations

    # Measure time for incorrect password
    start = time.perf_counter()
    for _ in range(iterations):
        verify_password("WrongPassword456", hashed)
    wrong_time = (time.perf_counter() - start) / iterations

    # Times should be similar (within 30% - bcrypt is designed for constant time)
    # Allow more tolerance since we're measuring Python overhead too
    time_diff_ratio = abs(correct_time - wrong_time) / max(correct_time, wrong_time)
    assert time_diff_ratio < 0.3, f"Timing difference too large: {time_diff_ratio:.2%}"


def test_hash_password_not_reversible() -> None:
    """Test hash cannot be reversed to original password."""
    password = "SecretPassword123"
    hashed = hash_password(password)

    # Hash should not contain original password
    assert password not in hashed

    # Hash should be longer than password
    assert len(hashed) > len(password)


def test_needs_rehash_detects_old_rounds() -> None:
    """Test needs_rehash detects hashes with lower cost factor."""
    # Simulate old hash with 10 rounds
    old_hash = "$2b$10$abcdefghijklmnopqrstuvwxyz0123456789"

    assert needs_rehash(old_hash, target_rounds=12) is True


def test_needs_rehash_current_rounds() -> None:
    """Test needs_rehash returns False for current cost factor."""
    # Current hash with 12 rounds
    current_hash = "$2b$12$abcdefghijklmnopqrstuvwxyz0123456789"

    assert needs_rehash(current_hash, target_rounds=12) is False


def test_needs_rehash_higher_rounds() -> None:
    """Test needs_rehash returns False for higher cost factor."""
    # Hash with 13 rounds (higher than target)
    future_hash = "$2b$13$abcdefghijklmnopqrstuvwxyz0123456789"

    assert needs_rehash(future_hash, target_rounds=12) is False


def test_needs_rehash_invalid_format() -> None:
    """Test needs_rehash returns True for invalid hash format."""
    invalid_hashes = [
        "invalid",
        "$2b$",
        "$2b$12",
        "notahash",
        "",
    ]

    for invalid_hash in invalid_hashes:
        assert needs_rehash(invalid_hash) is True


def test_generate_secure_token_length() -> None:
    """Test secure token generation produces correct length."""
    token = generate_secure_token(32)

    # URL-safe base64 encoding of 32 bytes
    assert len(token) > 40  # Base64 encoding adds ~33% length
    assert len(token) < 50


def test_generate_secure_token_uniqueness() -> None:
    """Test generated tokens are unique."""
    tokens = {generate_secure_token() for _ in range(100)}

    # All tokens should be unique
    assert len(tokens) == 100


def test_generate_secure_token_url_safe() -> None:
    """Test generated tokens are URL-safe."""
    token = generate_secure_token()

    # URL-safe characters only (a-z, A-Z, 0-9, -, _)
    import string

    allowed_chars = string.ascii_letters + string.digits + "-_"
    assert all(c in allowed_chars for c in token)


def test_generate_secure_token_custom_length() -> None:
    """Test token generation with custom byte length."""
    token_16 = generate_secure_token(16)
    token_64 = generate_secure_token(64)

    # Longer byte length produces longer token
    assert len(token_64) > len(token_16)


def test_hash_password_performance() -> None:
    """Test password hashing takes appropriate time (anti-brute-force)."""
    password = "TestPassword123"

    start = time.perf_counter()
    hash_password(password)
    duration = time.perf_counter() - start

    # Bcrypt with 12 rounds should take 50-500ms
    # This is intentionally slow to prevent brute force
    assert duration > 0.03, "Hashing too fast - may not be secure"
    assert duration < 2.0, "Hashing too slow - may impact performance"


def test_verify_password_performance() -> None:
    """Test password verification takes similar time as hashing."""
    password = "TestPassword123"
    hashed = hash_password(password)

    start = time.perf_counter()
    verify_password(password, hashed)
    duration = time.perf_counter() - start

    # Verification should also be slow (same cost as hashing)
    assert duration > 0.03, "Verification too fast"
    assert duration < 2.0, "Verification too slow"


def test_password_hash_includes_salt() -> None:
    """Test password hash includes salt (no rainbow table attacks)."""
    password = "CommonPassword123"

    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Different salts mean different hashes
    assert hash1 != hash2

    # Both should verify correctly
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_verify_password_rejects_tampered_hash() -> None:
    """Test verification fails if hash is modified."""
    password = "SecurePassword123"
    hashed = hash_password(password)

    # Tamper with hash
    tampered = hashed[:-5] + "XXXXX"

    # Should fail verification or raise exception
    try:
        result = verify_password(password, tampered)
        assert result is False
    except ValueError:
        # Also acceptable - bcrypt may reject invalid format
        pass


def test_long_password_handling() -> None:
    """Test handling of very long passwords."""
    # Bcrypt has a 72-byte limit, but we should handle gracefully
    long_password = "A" * 100
    hashed = hash_password(long_password)

    assert verify_password(long_password, hashed) is True


def test_password_with_null_bytes() -> None:
    """Test password containing null bytes (edge case)."""
    # Null bytes could cause issues with C implementations
    password = "Pass\x00word123"
    hashed = hash_password(password)

    # Should handle correctly
    assert verify_password(password, hashed) is True


def test_concurrent_hashing_safety() -> None:
    """Test multiple concurrent hashing operations are safe."""
    import concurrent.futures

    passwords = [f"Password{i}" for i in range(10)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        hashes = list(executor.map(hash_password, passwords))

    # All hashes should be unique
    assert len(set(hashes)) == len(passwords)

    # All should verify correctly
    for password, hashed in zip(passwords, hashes):
        assert verify_password(password, hashed) is True


def test_hash_password_deterministic_salt() -> None:
    """Test that hash includes randomly generated salt each time."""
    password = "TestPassword"

    # Generate multiple hashes
    hashes = [hash_password(password) for _ in range(5)]

    # All should be different (different salts)
    assert len(set(hashes)) == 5

    # But all should verify the same password
    for hashed in hashes:
        assert verify_password(password, hashed) is True


@pytest.mark.parametrize(
    "password",
    [
        "simple",
        "With Spaces",
        "UPPERCASE",
        "lowercase",
        "MixedCase123",
        "Special!@#$%^&*()",
        "Numbers1234567890",
        "Tab\there",
        "Newline\nhere",
    ],
)
def test_various_password_formats(password: str) -> None:
    """Test password hashing works with various formats."""
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
