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

from src.config import config
from src.logging_utils import get_logger, setup_logging
from pincer_sdk import PincerClient

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

    # Initialize Pincer Client
    # In a real app, this should be initialized once globally or via dependency injection
    async with PincerClient(
        base_url=config.pincer_url,
        webhook_secret=config.webhook_secret
    ) as pincer:
        
        # Report conversion using SDK
        result = await pincer.report_conversion(
            session_id=request.session_id,
            user_address=request.user_address,
            purchase_amount=request.purchase_amount,
            purchase_asset="USD",
            merchant_id="shake-shack"
        )
        
        webhook_sent = result.status == "success"
        webhook_id = result.webhook_id or "unknown"
        message = result.message or result.error or "Unknown result"

        if webhook_sent:
             logger.info(f"Webhook accepted by Pincer: {message}")
        else:
             logger.error(f"Webhook rejected by Pincer: {message}")

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
