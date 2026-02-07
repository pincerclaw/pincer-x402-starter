"""Pincer Facilitator and Sponsorship Service.

Main FastAPI application integrating:
- x402 payment verification
- Sponsored offer generation
- Merchant webhook handling
- Rebate settlement
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config, validate_config_for_service
from src.database import db
from src.logging_utils import (
    CorrelationIdContext,
    get_logger,
    set_correlation_id,
    setup_logging,
)
from src.models import (
    ConversionWebhook,
    PaymentVerificationRequest,
)

from src.pincer.payout import payout_engine
from src.pincer.verification import pincer_facilitator, verifier
from src.pincer.webhooks import WebhookHandler


# Pydantic models for x402 facilitator endpoints
class X402VerifyRequest(BaseModel):
    """x402 library standard verify request format."""
    x402Version: int = 2
    paymentPayload: dict  # camelCase from x402 library
    paymentRequirements: dict  # camelCase from x402 library

class SettleRequest(BaseModel):
    """Settle endpoint request body."""
    paymentPayload: dict
    paymentRequirements: dict

# Validate configuration
validate_config_for_service("pincer")

# Setup logging
setup_logging(config.log_level, config.log_format)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Pincer",
    description="x402 Facilitator + Sponsorship Service",
)

# Initialize webhook handler
webhook_handler = WebhookHandler(payout_engine)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    logger.info("Initializing Pincer service...")
    await db.initialize()
    await db.initialize_campaigns()
    logger.info("Pincer service initialized")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "pincer"}


@app.post("/verify")
async def verify_payment(request: X402VerifyRequest):
    """Verify an x402 payment.

    This is a standard x402 facilitator endpoint. Accepts the standard x402 library
    format and converts to internal format.

    Args:
        request: x402 verify request with paymentPayload and paymentRequirements.

    Returns:
        Payment verification response in x402 format.
    """
    import uuid
    
    # Generate session_id from request data for tracking
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    
    logger.info(f"Payment verification request, session: {session_id}")
    
    # Convert x402 format to internal format
    internal_request = PaymentVerificationRequest(
        session_id=session_id,
        payment_payload=request.paymentPayload,
        payment_requirements=request.paymentRequirements,
    )
    
    response = await verifier.verify_payment(internal_request)
    
    # Return in x402 library expected format
    return {
        "isValid": response.verified,
        "invalidReason": response.error if not response.verified else None,
        "payer": response.user_address,
        "sponsors": [s.model_dump() for s in response.sponsors] if response.sponsors else [],
    }


@app.post("/settle")
async def settle_payment(request: SettleRequest):
    """Settle an x402 payment on-chain.

    Args:
        request: Payment payload and requirements to settle.

    Returns:
        SettleResponse with success, transaction, network, and payer.
    """
    try:
        logger.info("Payment settlement request")
        result = await pincer_facilitator.settle_payment(
            payment_payload=request.paymentPayload,
            payment_requirements=request.paymentRequirements,
        )
        return result
    except Exception as e:
        logger.error(f"Settlement error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/supported")
async def get_supported():
    """Get supported payment kinds and extensions.

    Returns:
        SupportedResponse with kinds, extensions, and signers.
    """
    try:
        return pincer_facilitator.get_supported()
    except Exception as e:
        logger.error(f"Supported error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sponsors/{session_id}")
async def get_sponsors(session_id: str):
    """Get sponsor offers for a session.
    
    This endpoint allows resource servers to fetch sponsor offers
    directly when x402 middleware doesn't pass them through.
    
    Args:
        session_id: The payment session ID
        
    Returns:
        Dict with sponsors list
    """
    import uuid
    try:
        # Get active campaigns from DB (MVP: just take the first one)
        campaigns = await db.get_active_campaigns()
        
        if not campaigns:
            return {"sponsors": []}
            
        campaign = campaigns[0]
        
        if campaign and campaign.active and campaign.budget_remaining >= campaign.rebate_amount:
            offer_id = f"off-{uuid.uuid4().hex[:8]}"
            
            # Create coupons
            from src.models import Coupon, SponsoredOffer
            
            offer = SponsoredOffer(
                sponsor_id=campaign.campaign_id,
                merchant_name=campaign.merchant_name,
                offer_text=campaign.offer_text,
                rebate_amount=campaign.rebate_amount,
                rebate_asset=campaign.rebate_asset,
                rebate_network=campaign.rebate_network,
                coupons=campaign.coupons or [],
                checkout_url=f"{config.merchant_url}/checkout?session_id={session_id}&offer_id={offer_id}",
                session_id=session_id,
                offer_id=offer_id,
            )
            
            logger.info(f"Returning sponsor offer for session {session_id}")
            return {"sponsors": [offer.model_dump()]}
        
        return {"sponsors": []}
    except Exception as e:
        logger.error(f"Error getting sponsors: {e}")
        return {"sponsors": []}



@app.post("/webhooks/conversion")
async def receive_conversion_webhook(
    request: Request,
    x_webhook_signature: str = Header(None, alias="X-Webhook-Signature"),
    x_correlation_id: str = Header(None, alias="X-Correlation-Id"),
):
    """Receive merchant conversion webhook and trigger rebate settlement.

    This is the critical endpoint for the post-pay rebate flow.
    Implements idempotency, anti-replay, and authentication.

    Args:
        request: FastAPI request object.
        x_webhook_signature: HMAC signature for authenticity.
        x_correlation_id: Optional correlation ID.

    Returns:
        Webhook processing result.
    """
    with CorrelationIdContext(x_correlation_id):
        logger.info("Received merchant conversion webhook")

        # Validate signature header
        if not x_webhook_signature:
            logger.error("Missing X-Webhook-Signature header")
            raise HTTPException(
                status_code=401,
                detail="Missing X-Webhook-Signature header",
            )

        # Read raw payload for signature verification
        raw_payload = await request.body()

        try:
            # Parse webhook payload
            payload_dict = await request.json()
            webhook = ConversionWebhook(**payload_dict)

            logger.info(f"Processing webhook {webhook.webhook_id} for session {webhook.session_id}")

            # Process webhook with all reliability checks
            result = await webhook_handler.process_webhook(
                webhook=webhook,
                signature=x_webhook_signature,
                raw_payload=raw_payload,
            )

            # Return appropriate status code
            if result["status"] == "success":
                return result
            elif result["status"] == "error":
                # Log but still return 200 to prevent retries for permanent errors
                logger.error(f"Webhook processing error: {result.get('error')}")
                raise HTTPException(status_code=400, detail=result.get("error"))
            else:  # processing
                return result

        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid webhook payload")
        except Exception as e:
            logger.error(f"Webhook processing error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Pincer service on {config.pincer_host}:{config.pincer_port}")
    uvicorn.run(
        app,
        host=config.pincer_host,
        port=config.pincer_port,
        log_level=config.log_level.lower(),
    )
