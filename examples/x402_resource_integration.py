"""x402 Resource Integration (SVM Only).

Demonstrates creating a paywalled API that accepts Solana payments.
Connects to the deployed Pincer facilitator.

Usage:
    uv run python examples/x402_resource_integration.py
"""

import os
import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from x402.server import x402ResourceServer
from x402.mechanisms.svm.exact import ExactSvmServerScheme
from x402.http import PaymentOption
from x402.http.types import RouteConfig

from pincer_sdk import PincerClient
from pincer_sdk.facilitator import PincerFacilitatorClient
from pincer_sdk.middleware import PincerPaymentMiddleware

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

# Configuration
PINCER_URL = os.getenv("PINCER_URL", "https://pincer.zeabur.app")
SVM_ADDRESS = os.getenv("SVM_ADDRESS")
PORT = 8001

app = FastAPI(title="Example Resource (SVM)")

def create_app():
    if not SVM_ADDRESS:
        print("❌ Error: SVM_ADDRESS not found in .env")
        sys.exit(1)

    print(f"Connecting to Pincer: {PINCER_URL}")

    # 1. Initialize Pincer Client
    pincer_client = PincerClient(base_url=PINCER_URL)

    # Pre-define supported schemes to avoid startup HTTP calls that can deadlock
    supported_schemes_fallback = {
        "kinds": [
            {"x402Version": 2, "scheme": "exact", "network": "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", "extra": {}},
        ],
        "extensions": [],
        "signers": []
    }

    # 2. Create x402 server using Pincer's enhanced facilitator
    facilitator = PincerFacilitatorClient(pincer_client, supported_schemes=supported_schemes_fallback)
    server = x402ResourceServer(facilitator)
    
    # 2. Register Solana Support
    server.register("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", ExactSvmServerScheme())

    # 3. Define Routes
    routes = {
        "/recommendations": RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=SVM_ADDRESS,
                    price="$0.05", # 5 cents USD
                    network="solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
                ),
            ],
            description="Premium Recommendations (0.05 USD)",
        )
    }

    app.add_middleware(PincerPaymentMiddleware, routes=routes, server=server)
    return app

@app.get("/recommendations")
async def recommendations(request: Request):
    """Protected endpoint."""
    payment = getattr(request.state, "payment", None)
    if payment:
        print(f"DEBUG: Payment Attributes: {dir(payment)}")
        if hasattr(payment, "context"):
             print(f"DEBUG: Payment Context: {payment.context}")

    # Try to find payer address in common locations
    payer = "unknown"
    if payment:
        if hasattr(payment, "user_address"):
            payer = payment.user_address
        elif hasattr(payment, "payer"):
            payer = payment.payer
        elif hasattr(payment, "context") and isinstance(payment.context, dict):
            payer = payment.context.get("payer", "unknown")

    return {
        "status": "success",
        "message": "Premium recommendations accessed!",
        "payer": payer,
        "restaurants": [{"name": "Eleven Madison Park", "cuisine": "Fine Dining"}],
        "sponsors": getattr(payment, "sponsors", []) if payment else []
    }

if __name__ == "__main__":
    create_app()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
