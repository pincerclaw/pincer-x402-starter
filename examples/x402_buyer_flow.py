"""x402 Buyer Flow (Simplified).

Demonstrates buying content via x402 using Solana (SVM).
Connects to the deployed Pincer demo by default.

Usage:
    uv run python examples/x402_buyer_flow.py
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

# Default to deployed demo
RESOURCE_URL = os.getenv("RESOURCE_URL", "https://pincer.zeabur.app/demo/resource")
SVM_PRIVATE_KEY = os.getenv("SVM_PRIVATE_KEY")


async def main():
    print("🚀 Pincer x402 Buyer Flow")
    print(f"Target: {RESOURCE_URL}/recommendations")

    if not SVM_PRIVATE_KEY:
        print("❌ Error: SVM_PRIVATE_KEY not found in .env")
        return

    # 1. Initialize Client & Wallet
    client = x402Client()
    try:
        signer = KeypairSigner.from_base58(SVM_PRIVATE_KEY)
        register_exact_svm_client(client, signer)
        print(f"🔐 Wallet: {signer.address}")
    except Exception as e:
        print(f"❌ Wallet Error: {e}")
        return

    # 2. Make Request (Auto-handles 402 Payment)
    print("\nREQUEST: Accessing paywalled content...")
    
    try:
        async with x402HttpxClient(client) as http:
            response = await http.get(f"{RESOURCE_URL}/recommendations")
            await response.aread()

            if response.status_code == 200:
                print("\n✅ SUCCESS: Content received!")
                data = response.json()
                
                # Show results
                restaurants = data.get("restaurants", [])
                print(f"📋 Received {len(restaurants)} recommendations")
                
                sponsors = data.get("sponsors", [])
                if sponsors:
                    print(f"\n🎁 Sponsor Offer: {sponsors[0]['merchant_name']}")
                    print(f"   \"{sponsors[0]['offer_text']}\"")
                    print(f"   Session ID: {sponsors[0]['session_id']}")
            else:
                print(f"\n❌ FAILED: HTTP {response.status_code}")
                # print(response.text)

    except httpx.RequestError as e:
        print(f"\n❌ Connection Error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
