"""x402 Resource Server.

A generic x402-protected resource server that can be adapted for any
paywalled content. Based on Coinbase x402 FastAPI example.
"""

import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

# Add parent to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pincer_sdk.types import SponsoredOffer

from src.config import config, validate_config_for_service
from src.logging_utils import (
    CorrelationIdContext,
    get_logger,
    setup_logging,
)
import httpx
# from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption  <-- Removed
from x402.http import PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.mechanisms.svm.exact import ExactSvmServerScheme
from x402.schemas import AssetAmount, Network
from x402.server import x402ResourceServer

from src.pincer_sdk import PincerClient
from src.pincer_sdk.facilitator import PincerFacilitatorClient

# Validate configuration
validate_config_for_service("resource")

# Setup logging
setup_logging(config.log_level, config.log_format)
logger = get_logger(__name__)

# Type definitions for network constants
EVM_NETWORK: Network = config.evm_network  # type: ignore
SVM_NETWORK: Network = config.svm_network  # type: ignore


# Response schemas
class Restaurant(BaseModel):
    """Restaurant recommendation."""

    name: str
    cuisine: str
    rating: float
    price_level: int  # 1-4 ($-$$$$)
    description: str


class RecommendationsResponse(BaseModel):
    """Response containing restaurant recommendations."""

    restaurants: list[Restaurant]
    session_id: Optional[str] = None
    sponsors: list["SponsoredOffer"] = []


# Sample restaurant data (base list - does NOT include sponsored restaurants)
SAMPLE_RESTAURANTS = [
    Restaurant(
        name="Eleven Madison Park",
        cuisine="Contemporary American",
        rating=4.9,
        price_level=4,
        description="Elevated plant-based tasting menu in an Art Deco landmark",
    ),
    Restaurant(
        name="Peter Luger Steak House",
        cuisine="Steakhouse",
        rating=4.7,
        price_level=4,
        description="Historic Brooklyn steakhouse famous for dry-aged porterhouse",
    ),
    Restaurant(
        name="Joe's Pizza",
        cuisine="Pizza",
        rating=4.6,
        price_level=1,
        description="Classic New York slice joint since 1975",
    ),
    Restaurant(
        name="Gramercy Tavern",
        cuisine="American",
        rating=4.8,
        price_level=3,
        description="Contemporary American cuisine in an elegant tavern setting",
    ),
]

# Sponsored restaurant (injected when sponsor offer exists)
SHAKE_SHACK = Restaurant(
    name="Shake Shack",
    cuisine="Burgers",
    rating=4.5,
    price_level=2,
    description="Modern day roadside burger stand serving premium burgers and shakes",
)


# Create FastAPI app
app = FastAPI(title="Resource Server", description="x402-protected resource server")


# x402 Setup
logger.info("Initializing Pincer Client and x402 server...")
pincer_client = PincerClient(base_url=config.pincer_url)

# Create x402 server using Composition Pattern
# 1. Use Pincer's client (handles extra data like sponsors)
facilitator = PincerFacilitatorClient(pincer_client)
# 2. Pass it to the standard server
server = x402ResourceServer(facilitator)

# Register payment schemes
logger.info(f"Registering EVM scheme for network: {EVM_NETWORK}")
server.register(EVM_NETWORK, ExactEvmServerScheme())

logger.info(f"Registering SVM scheme for network: {SVM_NETWORK}")
server.register(SVM_NETWORK, ExactSvmServerScheme())

# Define route payment requirements
routes = {
    "GET /recommendations": RouteConfig(
        accepts=[
            # EVM payment option (USDC on Base Sepolia)
            PaymentOption(
                scheme="exact",
                pay_to=config.evm_address or config.treasury_evm_address,
                price=AssetAmount(
                    amount=str(int(config.content_price_usd * 1_000_000)),  # USDC has 6 decimals
                    asset=config.evm_usdc_address,
                    extra={"name": "USDC", "version": "2"},
                ),
                network=EVM_NETWORK,
            ),
            # SVM payment option (SOL on Solana Devnet)
            PaymentOption(
                scheme="exact",
                pay_to=config.svm_address or config.treasury_svm_address,
                price=f"${config.content_price_usd}",
                network=SVM_NETWORK,
            ),
        ],
        mime_type="application/json",
        description="Premium restaurant recommendations",
    ),
}

logger.info(f"Configured payment routes: {list(routes.keys())}")


# Add middleware to demonstrate simplified integration
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "resource"}


@app.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(request: Request) -> RecommendationsResponse:
    """Get premium restaurant recommendations (protected by x402 payment).

    This endpoint requires payment via x402. After payment verification,
    it returns restaurant recommendations.

    Returns:
        RecommendationsResponse with restaurants.
    """
    # Extract correlation ID from headers or generate one
    correlation_id = request.headers.get("x-correlation-id")
    if not correlation_id:
        correlation_id = f"corr-{uuid.uuid4().hex[:12]}"

    with CorrelationIdContext(correlation_id):
        logger.info("Processing recommendations request")
        
        # Payment is already verified by middleware if we reached here!
        
        # Payment is already verified by middleware if we reached here!
        # The x402 middleware populates request.state.payment with the verification result
        payment = getattr(request.state, "payment", None)
        sponsors = getattr(payment, "sponsors", []) if payment else []
        
        logger.info(f"Got {len(sponsors)} sponsors from middleware context")

        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        if sponsors:
            session_id = sponsors[0].session_id
            logger.info(f"Using session ID from sponsor: {session_id}")

        # Return recommendations and any active sponsor offers
        response = RecommendationsResponse(
            restaurants=SAMPLE_RESTAURANTS,
            session_id=session_id,
            sponsors=sponsors
        )

        logger.info(f"Returning {len(response.restaurants)} restaurants")

        return response


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Resource server on {config.resource_host}:{config.resource_port}")
    uvicorn.run(
        app,
        host=config.resource_host,
        port=config.resource_port,
        log_level=config.log_level.lower(),
    )
