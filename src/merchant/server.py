"""Shake Shack Demo Merchant Server.

Simulates a merchant checkout flow and sends conversion webhooks to Pincer.
"""

import hashlib
import hmac
import sys
import uuid
import json
import asyncio
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.logging_utils import get_logger, setup_logging

# Setup logging
setup_logging(config.log_level, config.log_format)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Shake Shack Demo",
    description="Demo merchant server for Pincer x402 flow",
)


class CheckoutRequest(BaseModel):
    """Checkout request from agent/user."""

    session_id: str
    user_address: str
    purchase_amount: float = 25.00  # Default burger order amount


class CheckoutResponse(BaseModel):
    """Checkout confirmation response."""

    order_id: str
    purchase_amount: float
    webhook_sent: bool
    webhook_id: str
    message: str


def create_webhook_signature(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for webhook.

    Args:
        payload: JSON payload as string.
        secret: Shared secret.

    Returns:
        Hex-encoded HMAC signature.
    """
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "shake-shack"}


@app.post("/checkout", response_model=CheckoutResponse)
async def checkout(request: CheckoutRequest) -> CheckoutResponse:
    """Simulate checkout and send conversion webhook to Pincer.

    Args:
        request: Checkout request with session_id and user_address.

    Returns:
        Checkout confirmation with webhook status.
    """
    order_id = f"order-{uuid.uuid4().hex[:8]}"
    webhook_id = f"wh-{uuid.uuid4().hex[:12]}"

    logger.info(
        f"Processing checkout: order={order_id}, session={request.session_id}, "
        f"user={request.user_address}, amount={request.purchase_amount:.2f}"
    )

    # Simulate payment processing delay
    await asyncio.sleep(0.5)

    # Prepare webhook payload
    webhook_payload = {
        "webhook_id": webhook_id,
        "session_id": request.session_id,
        "user_address": request.user_address,
        "purchase_amount": request.purchase_amount,
        "purchase_asset": "USD",
        "timestamp": datetime.utcnow().isoformat(),
        "merchant_id": "shake-shack",
    }

    # Convert to JSON string for signing
    payload_str = json.dumps(webhook_payload)

    # Create HMAC signature
    signature = create_webhook_signature(payload_str, config.webhook_secret)

    logger.info(f"Sending conversion webhook {webhook_id} to Pincer")

    # Send webhook to Pincer
    webhook_sent = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.pincer_url}/webhooks/conversion",
                json=webhook_payload,
                headers={
                    "X-Webhook-Signature": signature,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code in [200, 201]:
                webhook_sent = True
                webhook_response = response.json()
                logger.info(
                    f"Webhook accepted by Pincer: {webhook_response.get('status')}"
                )
            else:
                logger.error(
                    f"Webhook rejected by Pincer: {response.status_code} - {response.text}"
                )

    except Exception as e:
        logger.error(f"Error sending webhook to Pincer: {e}", exc_info=True)

    response_message = (
        f"Order confirmed! Webhook {'sent successfully' if webhook_sent else 'failed'}. "
        f"Rebate should be processed shortly."
    )

    return CheckoutResponse(
        order_id=order_id,
        purchase_amount=request.purchase_amount,
        webhook_sent=webhook_sent,
        webhook_id=webhook_id,
        message=response_message,
    )


@app.get("/")
async def root():
    """Landing page."""
    return {
        "merchant": "Shake Shack Demo",
        "description": "Demo merchant for Pincer x402 post-pay rebate flow",
        "endpoints": {
            "/checkout": "POST - Process checkout and trigger rebate webhook",
            "/health": "GET - Health check",
        },
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Shake Shack merchant server on {config.merchant_host}:{config.merchant_port}")
    uvicorn.run(
        app,
        host=config.merchant_host,
        port=config.merchant_port,
        log_level=config.log_level.lower(),
    )
