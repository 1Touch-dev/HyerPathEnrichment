"""Password hashing and verification using bcrypt."""

import secrets

import bcrypt  # type: ignore[import-not-found]


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with salt.

    Bcrypt has a 72-byte limit. Longer passwords are truncated.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hash string (includes salt and cost factor)
    """
    password_bytes = password.encode("utf-8")[:72]  # Bcrypt 72-byte limit
    salt = bcrypt.gensalt(rounds=12)  # Cost factor: 2^12 iterations
    hashed: bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash (constant-time comparison).

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash from database

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode("utf-8")[:72]  # Bcrypt 72-byte limit
    hashed_bytes = hashed_password.encode("utf-8")
    result: bool = bcrypt.checkpw(password_bytes, hashed_bytes)
    return result


def needs_rehash(hashed_password: str, target_rounds: int = 12) -> bool:
    """
    Check if a password hash needs to be rehashed (e.g., cost factor changed).

    Args:
        hashed_password: Existing bcrypt hash
        target_rounds: Desired cost factor (default 12)

    Returns:
        True if hash should be regenerated with new cost factor
    """
    try:
        # Bcrypt format: $2b$12$salthash...
        parts = hashed_password.split("$")
        if len(parts) < 4:
            return True

        current_rounds = int(parts[2])
        return current_rounds < target_rounds
    except (IndexError, ValueError):
        # Invalid hash format, needs rehash
        return True


def generate_secure_token(nbytes: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        nbytes: Number of random bytes (default 32 = 256 bits)

    Returns:
        URL-safe token string
    """
    return secrets.token_urlsafe(nbytes)
