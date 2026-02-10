"""Quick debug script to test x402 payment flow."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client

from src.config import config


async def test_payment():
    """Test a simple x402 payment."""
    print("🔍 Testing x402 payment flow...\n")
    
    print(f"SVM Address: {config.svm_address or 'Not set'}")
    print(f"Resource URL: {config.resource_url}")
    print(f"Pincer URL: {config.pincer_url}")
    print(f"Merchant URL: {config.merchant_url}")
    print(f"Content Price: ${config.content_price_usd}\n")
    
    # Create client
    client = x402Client()
    signer = KeypairSigner.from_base58(config.svm_private_key)
    register_exact_svm_client(client, signer)
    
    print(f"✅ Client created with address: {signer.address}\n")
    
    # Try request
    print("📡 Making request to /recommendations...\n")
    
    async with x402HttpxClient(client) as http:
        response = await http.get(
            f"{config.resource_url}/recommendations",
            headers={"X-Debug": "true"},
        )
        await response.aread()
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}\n")
        
        if response.status_code == 200:
            print("✅ Payment succeeded!")
            print(f"Response: {response.text[:200]}")
        else:
            print(f"❌ Payment failed: {response.status_code}")
            print(f"Response: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_payment())
