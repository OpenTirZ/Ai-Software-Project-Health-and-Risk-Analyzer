"""
GitHub Webhook Router
---------------------
FastAPI router for incoming GitHub webhook events:
- Verifies HMAC-SHA256 signature using GITHUB_WEBHOOK_SECRET
- Processes push, pull_request, and ping events
- Offloads heavy synchronization to FastAPI BackgroundTasks for rapid (<10s) responses
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse

from Backend.externalservies.webhook_service import (
    dispatch_event,
    is_delivery_processed,
    record_delivery,
    verify_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post(
    "/github",
    status_code=status.HTTP_200_OK,
    summary="GitHub Webhook Listener",
    description="Receives GitHub webhook events, verifies HMAC-SHA256 signature, and synchronizes data.",
)
async def github_webhook_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Handle incoming GitHub webhook events (push, pull_request, ping).
    """
    # 1. Fail closed if webhook secret is not configured on the server
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.error("Webhook processing aborted: GITHUB_WEBHOOK_SECRET environment variable is missing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret is not configured on the server.",
        )

    # 2. Extract GitHub webhook headers
    signature_header = request.headers.get("X-Hub-Signature-256")
    event_type = request.headers.get("X-GitHub-Event")
    delivery_id = request.headers.get("X-GitHub-Delivery")

    # 3. Read raw body bytes BEFORE JSON decoding for cryptographic signature verification
    raw_body = await request.body()

    if not signature_header:
        logger.warning("Rejected webhook request: missing X-Hub-Signature-256 header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header.",
        )

    # 4. Verify signature in constant time
    if not verify_signature(raw_body, signature_header, secret):
        logger.warning("Rejected webhook request: invalid HMAC signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    # 5. Decode JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Rejected webhook request: malformed JSON payload (%s).", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    if not event_type:
        logger.warning("Rejected webhook request: missing X-GitHub-Event header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-GitHub-Event header.",
        )

    # 6. Idempotency check: fast-return if delivery ID was already processed
    if delivery_id and is_delivery_processed(delivery_id):
        logger.info("Delivery %s has already been processed. Returning 200.", delivery_id)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "duplicate",
                "delivery_id": delivery_id,
                "message": "Delivery already processed.",
            },
        )

    # 7. Fast responses for ping events
    if event_type == "ping":
        result = dispatch_event(event_type, payload, delivery_id)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    # 8. Return 200 ignored for unsupported events
    if event_type not in ("push", "pull_request"):
        result = dispatch_event(event_type, payload, delivery_id)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    # 9. Offload heavy push / PR synchronizations to BackgroundTasks (< 10s response)
    background_tasks.add_task(dispatch_event, event_type, payload, delivery_id)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "accepted",
            "event": event_type,
            "delivery_id": delivery_id,
            "message": f"Webhook event '{event_type}' accepted for background processing.",
        },
        background=background_tasks,
    )
