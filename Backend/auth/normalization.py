"""
Email normalization utilities.
"""
from typing import Any
from pydantic import BaseModel, EmailStr, ValidationError


class _EmailValidator(BaseModel):
    email: EmailStr


def normalize_email(email: str | None) -> str:
    """
    Normalize an email address for consistent storage and lookup:
    - Strips leading and trailing whitespace
    - Converts all characters to lowercase
    - Returns empty string for None or empty inputs
    """
    if not email:
        return ""
    return email.strip().lower()


def canonicalize_email(email: Any) -> str:
    """
    Canonicalize an email address for consistent database storage, unique indexing,
    and lookups across all entry points (signup, direct persistence, and migration).
    1. Strips and lowercases via B1 normalize_email().
    2. Applies Pydantic EmailStr IDNA and Unicode normalization (e.g. decoding
       Punycode xn--... to Unicode, full-width Unicode characters to ASCII).
    3. Rejects invalid email addresses by raising ValueError with explicit ValidationError handling.
    """
    if email is None or not isinstance(email, str) or email == "":
        raise ValueError("User email is required.")
    base = normalize_email(email)
    if not base:
        raise ValueError("User email must not be empty after normalization.")
    try:
        validated = _EmailValidator(email=base)
        return normalize_email(str(validated.email))
    except ValidationError as exc:
        raise ValueError(f"Invalid email address format: {email!r}") from exc
