
import pytest
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

from src.resource.server import app as resource_app_instance
from src.pincer.server import app as pincer_app_instance
from src.config import config
from x402.client import x402Client
from x402.http.clients import x402_httpx_transport
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact import register_exact_svm_client
from solders.keypair import Keypair

# Mock configuration for testing
@pytest.fixture(autouse=True)
def mock_config():
    with patch("src.config.config.svm_private_key", "5123456789abcdef" * 5), \
         patch("src.config.config.svm_address", "11111111111111111111111111111111"), \
         patch("src.config.config.treasury_svm_address", "11111111111111111111111111111111"), \
         patch("src.config.config.treasury_svm_private_key", "5treasury" * 10), \
         patch("src.config.config.content_price_usd", 0.01):
        yield

@pytest.fixture
def resource_app():
    return resource_app_instance

@pytest.fixture
def pincer_app():
    return pincer_app_instance

@pytest.mark.asyncio
async def test_full_payment_flow(resource_app):
    """Test the complete 402 payment flow using local resource server."""
    
    # Setup client
    client = x402Client()
    
    # Register a dummy signer for the test
    # We use the key from the mock config or just a random one, but the network must match
    # what the server requests.
    # Server requests: SVM_NETWORK = config.svm_network
    # We need to know what that is. It's likely "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1" (devnet) from logs.
    
    # We can read it from the config patch, but config is imported at top level.
    # Let's just use a real keypair and register it.
    # Generate a valid keypair using solders
    keypair = Keypair()
    # KeypairSigner.from_base58 expects the base58 string representation of the secret key
    dummy_signer = KeypairSigner.from_base58(str(keypair))
    register_exact_svm_client(client, dummy_signer)
    
    # Let's mock the server's verify_payment to always succeed for this test
    # to isolate protocol flow from blockchain validation
    with patch("x402.server.x402ResourceServer.verify_payment") as mock_verify:
        # Mock what verify_payment returns
        mock_verify.return_value = MagicMock(
            type="payment-verified",
            payment_payload={},
            payment_requirements={},
            sponsors=[
                {
                    "merchant_name": "Pizza Hut",
                    "offer_text": "Free Coke",
                    "rebate_amount": 0.05,
                    "sponsor_id": "sp_123",
                    "merchant_name": "Pizza Hut",
                    "offer_text": "Get $5 back",
                    "rebate_amount": 5.0,
                    "rebate_asset": "USDC",
                    "rebate_network": "eip155:84532",
                    "checkout_url": "http://checkout",
                    "session_id": "sess_123",
                    "offer_id": "off_123",
                    "coupons": []
                }
            ]
        )
        # We also need the Mock object to have 'sponsors' attribute for our middleware hack
        mock_verify.return_value.sponsors = [
            {
                "sponsor_id": "sp_123",
                "merchant_name": "Pizza Hut",
                "offer_text": "Get $5 back",
                "rebate_amount": 5.0,
                "rebate_asset": "USDC",
                "rebate_network": "eip155:84532",
                "checkout_url": "http://checkout",
                "session_id": "sess_123",
                "offer_id": "off_123",
                "coupons": []
            }
        ]
        
        transport = ASGITransport(app=resource_app)
        # Create payment-aware transport wrapping the ASGI transport
        payment_transport = x402_httpx_transport(client, transport=transport)
        
        async with AsyncClient(transport=payment_transport, base_url="http://test") as http_client:
            
            # Make request
            response = await http_client.get(
                "/recommendations", 
                headers={"X-Correlation-Id": "test-flow"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify content
            assert "restaurants" in data
            assert len(data["restaurants"]) > 0
            
            # Verify sponsors were injected by middleware
            assert "sponsors" in data
            assert data["sponsors"][0]["merchant_name"] == "Pizza Hut"
