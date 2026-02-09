"""Integration tests for PincerPaymentMiddleware."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from src.pincer_sdk.middleware import PincerPaymentMiddleware
from x402.http.types import HTTPRequestContext, HTTPProcessResult, RouteConfig
from x402.schemas.responses import VerifyResponse, PaymentPayload, PaymentRequirements

# Mock data
MOCK_SPONSOR = {
    "sponsor_id": "sp-123",
    "merchant_name": "Test Sponsor",
    "offer_text": "Test Offer",
    "rebate_amount": 10.0,
    "rebate_asset": "USDC",
    "rebate_network": "solana:mainnet",
    "coupons": [],
    "checkout_url": "http://checkout",
    "session_id": "sess-123",
    "offer_id": "off-123"
}

@pytest.fixture
def mock_server():
    """Mock the x402 resource server."""
    server = MagicMock()
    # Mock verify_payment to return a response with sponsors
    async def mock_verify(*args, **kwargs):
        response = VerifyResponse(is_valid=True)
        # Inject sponsors (simulating monkey-patch effect)
        response.sponsors = [MagicMock(**MOCK_SPONSOR)]
        # Also set in __dict__ just in case
        response.__dict__["sponsors"] = [MagicMock(**MOCK_SPONSOR)]
        return response
        
    server.verify_payment = AsyncMock(side_effect=mock_verify)
    return server

def test_middleware_captures_sponsors(mock_server):
    """Test that middleware captures sponsors and injects them into request state."""
    app = FastAPI()
    
    # Define a simple route that returns the sponsors from state
    @app.get("/protected")
    def protected_route(request: Request):
        return {"sponsors": [s.sponsor_id for s in request.state.payment.sponsors]}

    # Mock routes config
    routes = {
        "/protected": RouteConfig(
            accepts=[], # Mocked
            mime_type="application/json",
            description="Protected"
        )
    }

    # Add middleware
    app.add_middleware(PincerPaymentMiddleware, routes=routes, server=mock_server)

    client = TestClient(app)
    
    # We need to mock the internal HTTP server's process_http_request 
    # because it's hard to mock the generator flow from outside.
    # Alternatively, we rely on PincerHTTPResourceServer behaving correctly with our mock server.
    
    # To test the integration properly without a real network, we should mock 
    # PincerHTTPResourceServer.process_http_request to return a specific result
    
    with patch("src.pincer_sdk.middleware.PincerHTTPResourceServer.process_http_request") as mock_process:
        # Construct valid objects
        reqs = PaymentRequirements(
            scheme="exact",
            network="eip155:1",
            asset="0x0000000000000000000000000000000000000000",
            amount="100",
            pay_to="0x0000000000000000000000000000000000000000",
            max_timeout_seconds=3600
        )

        result = HTTPProcessResult(type="payment-verified")
        result.payment_payload = PaymentPayload(
            payload={"signature": "sig"},
            accepted=reqs
        )
        result.payment_requirements = reqs
        # Manually attach sponsors as the class does
        expected_sponsors = [MagicMock(**MOCK_SPONSOR)]
        setattr(result, "sponsors", expected_sponsors)
        
        mock_process.return_value = result
        
        # Also allow requires_payment to return True
        with patch("src.pincer_sdk.middleware.PincerHTTPResourceServer.requires_payment", return_value=True):
             response = client.get("/protected")
             
             assert response.status_code == 200
             assert response.json()["sponsors"] == ["sp-123"]
             
    # Test passed!
