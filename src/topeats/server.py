"""TopEats Paywalled Content Server.

Based on Coinbase x402 FastAPI example, adapted to integrate with Pincer for
sponsored offer injection after payment verification.
"""

import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

# Add parent to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config, validate_config_for_service
from src.logging_utils import (
    CorrelationIdContext,
    get_logger,
    setup_logging,
)
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.mechanisms.svm.exact import ExactSvmServerScheme
from x402.schemas import AssetAmount, Network
from x402.server import x402ResourceServer

# Validate configuration
validate_config_for_service("topeats")

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


# Sample restaurant data
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
        name="Shake Shack",
        cuisine="Burgers",
        rating=4.5,
        price_level=2,
        description="Modern day roadside burger stand serving premium burgers and shakes",
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


# Create FastAPI app
app = FastAPI(title="TopEats", description="Premium restaurant recommendations powered by x402")


# x402 Setup
logger.info("Initializing x402 facilitator client...")
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=config.facilitator_url))
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


# Add x402 middleware
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)



@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "topeats"}


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

        session_id = f"sess-{uuid.uuid4().hex[:12]}"

        # Check if payment was verified (set by middleware)
        payment_payload = getattr(request.state, "payment_payload", None)

        if payment_payload:
            logger.info(f"Payment verified, session_id: {session_id}")

        response = RecommendationsResponse(
            restaurants=SAMPLE_RESTAURANTS,
            session_id=session_id,
        )

        logger.info(f"Returning {len(response.restaurants)} restaurants")

        return response


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting TopEats server on {config.topeats_host}:{config.topeats_port}")
    uvicorn.run(
        app,
        host=config.topeats_host,
        port=config.topeats_port,
        log_level=config.log_level.lower(),
    )
