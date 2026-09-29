"""
Security utilities:
  - Password hashing / verification (bcrypt 4+/5+ native)
  - JWT access token creation / decoding
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from jose import jwt

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# ---------------------------------------------------------------------------
# Password hashing  (uses bcrypt directly — passlib is NOT compatible with bcrypt 5.x)
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "CHANGE_ME_in_production")
_ALGORITHM: str = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Encode a JWT access token.

    Args:
        data: Payload to embed (must include a 'sub' claim, e.g. user id).
        expires_delta: Custom expiry. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Signed JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Returns:
        Decoded payload dict.

    Raises:
        JWTError: If the token is invalid or expired.
    """
    return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
