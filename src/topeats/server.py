"""TopEats Paywalled Content Server.

Based on Coinbase x402 FastAPI example, adapted to integrate with Pincer for
sponsored offer injection after payment verification.
"""

import sys
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel

# Add parent to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config, validate_config_for_service
from src.logging_utils import (
    CorrelationIdContext,
    get_correlation_id,
    get_logger,
    set_correlation_id,
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


class SponsoredOffer(BaseModel):
    """Sponsored offer from Pincer."""

    sponsor_id: str
    merchant_name: str
    offer_text: str
    rebate_amount: str
    merchant_url: str
    session_id: str
    offer_id: str


class RecommendationsResponse(BaseModel):
    """Response containing restaurant recommendations and optional sponsored offers."""

    restaurants: list[Restaurant]
    sponsored_offers: list[SponsoredOffer] = []
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


async def fetch_sponsored_offers(session_id: str, user_address: str, network: str) -> list[SponsoredOffer]:
    """Fetch sponsored offers from Pincer service after payment verification.

    Args:
        session_id: Payment session ID.
        user_address: User wallet address.
        network: Network identifier.

    Returns:
        List of sponsored offers.
    """
    try:
        correlation_id = get_correlation_id()
        logger.info(
            f"Fetching sponsored offers for session {session_id} from Pincer service"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.pincer_url}/offers",
                json={
                    "session_id": session_id,
                    "user_address": user_address,
                    "network": network,
                    "amount_paid_usd": config.content_price_usd,
                    "correlation_id": correlation_id,
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                offers = [SponsoredOffer(**offer) for offer in data.get("offers", [])]
                logger.info(f"Received {len(offers)} sponsored offers from Pincer")
                return offers
            else:
                logger.warning(
                    f"Failed to fetch offers from Pincer: {response.status_code} - {response.text}"
                )
                return []

    except Exception as e:
        logger.error(f"Error fetching sponsored offers: {e}", exc_info=True)
        return []


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "topeats"}


@app.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(request: Request) -> RecommendationsResponse:
    """Get premium restaurant recommendations (protected by x402 payment).

    This endpoint requires payment via x402. After payment verification,
    it returns restaurant recommendations and may include sponsored offers
    from Pincer.

    Returns:
        RecommendationsResponse with restaurants and optional sponsored offers.
    """
    # Extract correlation ID from headers or generate one
    correlation_id = request.headers.get("x-correlation-id")
    if not correlation_id:
        correlation_id = f"corr-{uuid.uuid4().hex[:12]}"

    with CorrelationIdContext(correlation_id):
        logger.info("Processing recommendations request")

        # Check if payment was verified (set by middleware)
        payment_payload = getattr(request.state, "payment_payload", None)

        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        sponsored_offers = []

        if payment_payload:
            # Payment was verified, try to fetch sponsored offers
            logger.info(f"Payment verified, session_id: {session_id}")

            # Extract user address from payment payload
            # This varies by network/scheme, so we need to handle both
            user_address = None
            network = None

            try:
                # Try to extract from payment payload
                if hasattr(payment_payload, "from_address"):
                    user_address = payment_payload.from_address
                elif hasattr(payment_payload, "from"):
                    user_address = payment_payload.from_
                elif isinstance(payment_payload, dict):
                    user_address = payment_payload.get("from") or payment_payload.get("from_address")

                # Try to extract network
                if hasattr(payment_payload, "network"):
                    network = payment_payload.network
                elif isinstance(payment_payload, dict):
                    network = payment_payload.get("network")

                if user_address and network:
                    sponsored_offers = await fetch_sponsored_offers(session_id, user_address, network)
                else:
                    logger.warning("Could not extract user_address or network from payment_payload")

            except Exception as e:
                logger.error(f"Error extracting payment info: {e}", exc_info=True)

        response = RecommendationsResponse(
            restaurants=SAMPLE_RESTAURANTS,
            sponsored_offers=sponsored_offers,
            session_id=session_id,
        )

        logger.info(
            f"Returning {len(response.restaurants)} restaurants "
            f"and {len(response.sponsored_offers)} offers"
        )

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
