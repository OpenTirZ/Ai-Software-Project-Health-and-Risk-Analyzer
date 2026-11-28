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
    if smtp_user:
        smtp_user = smtp_user.strip()
    if smtp_pass:
        smtp_pass = smtp_pass.replace(" ", "").strip()
    smtp_from = (
        os.environ.get("SMTP_FROM")
        or os.environ.get("SMTP_USER")
        or os.environ.get("MAIL_FROM")
        or "kavachofficial@gmail.com"
    )

    if not smtp_host:
        logger.info(
            "SMTP_HOST not set. Mock dispatch: OTP [%s] sent to [%s]",
            code,
            to_email,
        )
        return True

    msg = EmailMessage()
    msg["Subject"] = "Your KAVACH Verification Code"
    msg["From"] = f"KAVACH Security <{smtp_from}>" if "<" not in smtp_from else smtp_from
    msg["To"] = to_email

    plain_content = (
        f"KAVACH — Software Project Health & Risk Intelligence\n\n"
        f"Hello,\n\n"
        f"Your one-time verification code is: {code}\n\n"
        f"This code will expire in 5 minutes. If you did not request this verification code, "
        f"please disregard this message.\n\n"
        f"Security notice: Never share your one-time password with anyone.\n\n"
        f"— KAVACH Security Team"
    )
    # Minimalist, clean HTML optimized for inbox deliverability (avoids spam filters)
    # Uses KAVACH primary brand color: #0F4C47 (Deep Forest Teal)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KAVACH Verification Code</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 460px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0;">
    <tr>
      <td style="padding: 28px 24px 16px 24px; border-bottom: 2px solid #0F4C47;">
        <span style="font-size: 20px; font-weight: 700; letter-spacing: 1.5px; color: #0F4C47;">KAVACH</span>
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-top: 2px;">Software Project Health &amp; Risk Intelligence</div>
      </td>
    </tr>
    <tr>
      <td style="padding: 24px;">
        <p style="font-size: 15px; color: #334155; margin: 0 0 16px 0; line-height: 1.5;">Hello,</p>
        <p style="font-size: 14px; color: #475569; margin: 0 0 20px 0; line-height: 1.5;">Use the one-time verification code below to complete your authentication:</p>
        <div style="background-color: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 6px; padding: 18px; text-align: center; margin: 0 0 20px 0;">
          <span style="font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #0F4C47; font-family: monospace;">{code}</span>
        </div>
        <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 0 0 8px 0;">This code expires in <strong>5 minutes</strong>. If you did not make this request, you can safely ignore this email.</p>
        <p style="font-size: 12px; color: #94a3b8; line-height: 1.4; margin: 0;">Never share this verification code with anyone.</p>
      </td>
    </tr>
    <tr>
      <td style="padding: 16px 24px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
        <p style="font-size: 11px; color: #94a3b8; margin: 0;">&copy; KAVACH Security &bull; Project Health &amp; Risk Analyzer</p>
      </td>
    </tr>
  </table>
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
