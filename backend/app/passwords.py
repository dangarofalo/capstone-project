"""Password hashing for dashboard users (PBKDF2-SHA256, Python standard library).

Stored format: pbkdf2_sha256$<iterations>$<salt>$<hash>, so the iteration count can be
raised later without breaking existing passwords.
"""
import base64
import hashlib
import hmac
import secrets

from . import config


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = config.PASSWORD_ITERATIONS
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    # Constant-time comparison so response timing doesn't leak how close a guess was.
    return hmac.compare_digest(_b64(digest), expected)


def password_problem(password: str) -> str | None:
    """Return why a new password is too weak, or None if it is acceptable."""
    if len(password) < config.PASSWORD_MIN_LENGTH:
        return f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters."
    if password.isalpha() or password.isdigit():
        return "Password must mix letters with numbers or symbols."
    return None
