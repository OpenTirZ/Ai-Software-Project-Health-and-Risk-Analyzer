"""
Audit Middleware for AI Software Project Health & Risk Analyzer (TASK-SP4-08 / Issue #115)
------------------------------------------------------------------------------------------
Intercepts state-changing HTTP requests (POST, PUT, PATCH, DELETE) and records structured
audit event logs asynchronously via non-blocking worker threads.

Key Features:
- Intercepts state-changing methods only (POST, PUT, PATCH, DELETE).
- Read-only methods (GET, HEAD, OPTIONS) are bypassed without audit overhead.
- Authenticated user ID is obtained strictly from cryptographically verified JWT tokens
  or verified request state; untrusted client headers (e.g. X-User-ID) are ignored.
- Captures accurate UTC timestamps, client IP, route path, method, and response status.
- Non-blocking persistence using asyncio.to_thread wrapping the synchronous repository
  persistence layer (create_audit_log).
- Resilient: persistence failures are safely logged and NEVER fail the user request.
- No sensitive data (passwords, JWTs, API keys) is ever logged or stored in audit records.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from Backend.auth.security import decode_access_token
from Backend import persistence

logger = logging.getLogger(__name__)

# HTTP methods that mutate state and require auditing
STATE_CHANGING_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}


def get_client_ip(request: Request) -> str:
    """Extract the client IP address.

    To protect against IP-spoofing attacks, proxy headers (X-Forwarded-For, X-Real-IP)
    are ignored unless TRUST_FORWARDED_FOR is explicitly set to true.
    """
    trust_forwarded = os.environ.get("TRUST_FORWARDED_FOR", "").strip().lower() in ("true", "1")
    if trust_forwarded:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def extract_authenticated_user_id(request: Request) -> Optional[str]:
    """Resolve the authenticated user ID strictly through cryptographic verification.

    Never trusts client-supplied headers like X-User-ID, query parameters, or request bodies.
    Inspects request.state (if populated by dependencies) and decodes Bearer JWT tokens.
    """
    # 1. Check request.state if populated by upstream/dependency authentication
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return str(user_id)

    state_user = getattr(request.state, "user", None)
    if isinstance(state_user, dict):
        uid = state_user.get("_id") or state_user.get("id")
        if uid:
            return str(uid)

    # 2. Extract and cryptographically verify Bearer token from Authorization header
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            payload = decode_access_token(token)
            sub = payload.get("sub")
            if sub:
                return str(sub)
        except Exception:
            # Token invalid, tampered, or expired
            return None

    return None


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware to intercept state-changing requests and log audit events asynchronously."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # Fast path: bypass non-state-changing requests (GET, HEAD, OPTIONS)
        if request.method not in STATE_CHANGING_METHODS:
            return await call_next(request)

        # Capture initial metadata
        timestamp = datetime.now(timezone.utc)
        route = request.url.path
        method = request.method
        client_ip = get_client_ip(request)

        status_code = 500
        response: Optional[Response] = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            # Record audit entry even on uncaught exceptions before re-raising
            user_id = extract_authenticated_user_id(request)
            audit_entry = {
                "timestamp": timestamp,
                "createdAt": timestamp,
                "user_id": user_id,
                "actor_id": user_id,
                "route": route,
                "path": route,
                "method": method,
                "action": f"{method} {route}",
                "status_code": status_code,
                "client_ip": client_ip,
            }
            try:
                await asyncio.to_thread(persistence.create_audit_log, audit_entry)
            except Exception as audit_exc:
                logger.error("Audit log persistence failed on uncaught exception: %s", audit_exc)
            raise
        finally:
            if response is not None:
                # Resolve authenticated user identity after request processing
                user_id = extract_authenticated_user_id(request)
                audit_entry = {
                    "timestamp": timestamp,
                    "createdAt": timestamp,
                    "user_id": user_id,
                    "actor_id": user_id,
                    "route": route,
                    "path": route,
                    "method": method,
                    "action": f"{method} {route}",
                    "status_code": status_code,
                    "client_ip": client_ip,
                }
                # Asynchronously persist audit log without allowing persistence errors to break request
                try:
                    await asyncio.to_thread(persistence.create_audit_log, audit_entry)
                except Exception as audit_exc:
                    logger.error("Audit log persistence failed: %s", audit_exc)
