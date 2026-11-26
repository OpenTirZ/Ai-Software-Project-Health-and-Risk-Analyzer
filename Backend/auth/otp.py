"""
OTP (One-Time Password) Service for Multi-Factor & Passwordless Authentication.

Features:
- Cryptographically secure 6-digit numeric OTP generation.
- Salted SHA-256 hashing before storing in MongoDB.
- 5-minute TTL expiration.
- Brute-force throttling (max 3 failed attempts before lockout).
- Replay attack prevention (immediate invalidation upon successful verification).
- SMTP email dispatch with HTML + plain text fallback.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import logging
import os
import re
import secrets
import smtplib
from typing import Optional, Tuple

from Backend.auth.normalization import normalize_email
from Backend.database import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------
OTP_LENGTH: int = 6
DEFAULT_OTP_TTL_SECONDS: int = 300  # 5 minutes
DEFAULT_MAX_ATTEMPTS: int = 3
OTP_COLLECTION_NAME: str = "user_otps"


def _get_otp_collection():
    """Retrieve the MongoDB collection for storing OTPs."""
    return db[OTP_COLLECTION_NAME]


def _make_aware(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# OTP Generation & Cryptographic Hashing
# ---------------------------------------------------------------------------

def generate_otp(length: int = OTP_LENGTH) -> str:
    """
    Generate a cryptographically secure numeric OTP of the specified length.
    """
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def hash_otp(code: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Compute salted SHA-256 digest for an OTP code.

    Returns:
        Tuple of (hex_digest, salt).
    """
    if not salt:
        salt = secrets.token_hex(16)
    payload = f"{salt}:{code}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return digest, salt


def verify_otp_hash(code: str, stored_hash: str, salt: str) -> bool:
    """
    Verify an OTP code against its stored salted hash using constant-time comparison.
    """
    payload = f"{salt}:{code}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return hmac.compare_digest(digest, stored_hash)


# ---------------------------------------------------------------------------
# Database Persistence & Verification Logic
# ---------------------------------------------------------------------------

def save_otp(
    email: str,
    code: str,
    ttl_seconds: int = DEFAULT_OTP_TTL_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict:
    """
    Store a salted hash of the OTP code in MongoDB with expiration and attempt counters.
    Any existing OTP for this email is replaced/overwritten.
    """
    clean_email = normalize_email(email)
    digest, salt = hash_otp(code)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)

    record = {
        "email": clean_email,
        "otp_hash": digest,
        "salt": salt,
        "attempts": 0,
        "max_attempts": max_attempts,
        "created_at": now,
        "expires_at": expires_at,
    }

    collection = _get_otp_collection()
    collection.update_one(
        {"email": clean_email},
        {"$set": record},
        upsert=True,
    )
    return record


def verify_otp(email: str, code: str) -> Tuple[bool, str]:
    """
    Verify an OTP code for a given email address.

    Returns:
        (is_valid: bool, error_message: str)
        If valid, (True, "").
        If invalid, (False, "Reason for failure").
    """
    clean_email = normalize_email(email)
    collection = _get_otp_collection()
    record = collection.find_one({"email": clean_email})

    if not record:
        return False, "Invalid or expired OTP. Please request a new code."

    now = datetime.now(timezone.utc)
    expires_at = _make_aware(record.get("expires_at", now))

    # Check expiration
    if now > expires_at:
        collection.delete_one({"_id": record["_id"]})
        return False, "OTP has expired. Please request a new code."

    attempts = int(record.get("attempts", 0))
    max_attempts = int(record.get("max_attempts", DEFAULT_MAX_ATTEMPTS))

    # Check brute-force attempt lockout
    if attempts >= max_attempts:
        collection.delete_one({"_id": record["_id"]})
        return False, "Too many failed attempts. Please request a new OTP."

    stored_hash = record.get("otp_hash", "")
    salt = record.get("salt", "")

    if verify_otp_hash(code, stored_hash, salt):
        # Successful verification: delete record immediately (replay attack prevention)
        collection.delete_one({"_id": record["_id"]})
        return True, ""

    # Incorrect code: increment failed attempts
    new_attempts = attempts + 1
    if new_attempts >= max_attempts:
        collection.delete_one({"_id": record["_id"]})
        return False, "Too many failed attempts. Please request a new OTP."

    collection.update_one(
        {"_id": record["_id"]},
        {"$set": {"attempts": new_attempts}},
    )
    remaining = max_attempts - new_attempts
    return False, f"Invalid OTP code. {remaining} attempt(s) remaining."


# ---------------------------------------------------------------------------
# Email Dispatch
# ---------------------------------------------------------------------------

def send_otp_email(to_email: str, code: str) -> bool:
    """
    Dispatch an OTP email using standard SMTP.
    Falls back gracefully if SMTP is not configured in environment.
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS") or os.environ.get("SMTP_PASSWORD")
    smtp_from = (
        os.environ.get("SMTP_FROM")
        or os.environ.get("MAIL_FROM")
        or "no-reply@aegis-ai.internal"
    )

    if not smtp_host:
        logger.info(
            "SMTP_HOST not set. Mock dispatch: OTP [%s] sent to [%s]",
            code,
            to_email,
        )
        return True

    msg = EmailMessage()
    msg["Subject"] = "Your Aegis AI Verification Code"
    msg["From"] = smtp_from
    msg["To"] = to_email

    plain_content = (
        f"Hello,\n\n"
        f"Your Aegis AI verification code is: {code}\n\n"
        f"This code will expire in 5 minutes. If you did not request this code, "
        f"please disregard this message.\n\n"
        f"— Aegis AI Security Team"
    )
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; margin: 0; padding: 24px;">
  <div style="max-width: 480px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <h2 style="color: #111827; margin-top: 0;">Verification Code</h2>
    <p style="color: #4b5563; font-size: 15px;">Use the following one-time password to complete your authentication:</p>
    <div style="background-color: #f3f4f6; border-radius: 6px; padding: 16px; text-align: center; margin: 24px 0;">
      <span style="font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #1d4ed8; font-family: monospace;">{code}</span>
    </div>
    <p style="color: #6b7280; font-size: 13px; line-height: 1.5;">This code will expire in <strong>5 minutes</strong>. If you did not make this request, you can safely ignore this email.</p>
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;" />
    <p style="color: #9ca3af; font-size: 12px; margin: 0;">&copy; Aegis AI &bull; Project Health &amp; Risk Analyzer</p>
  </div>
</body>
</html>
"""
    msg.set_content(plain_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        logger.info("Successfully sent OTP email to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        return False
