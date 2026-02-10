
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client

from src.config import config


async def main():
    print("🚀 Starting Minimal x402 Agent...")

    # 1. Initialize Client & Wallet
    client = x402Client()
    
    if config.svm_private_key:
        signer = KeypairSigner.from_base58(config.svm_private_key)
        register_exact_svm_client(client, signer)
        print(f"🔐 Wallet: {signer.address} (Solana)")
    else:
        print("❌ Error: SVM_PRIVATE_KEY not found in .env")
        return

    # 2. Make Request (Auto-handles 402 Payment)
    print("📡 Requesting content...")
    
    async with x402HttpxClient(client) as http:
        response = await http.get(f"{config.resource_url}/recommendations")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Received data: {data}")
            restaurants = data.get("restaurants", [])
            sponsors = data.get("sponsors", [])
            
            print(f"\n✅ Success! Received {len(restaurants)} items.")
            print(f"🍽️  First Item: {restaurants[0]['name']} ({restaurants[0]['cuisine']})")
            
            if sponsors:
                print(f"🎁 Sponsor: {sponsors[0]['merchant_name']} - {sponsors[0]['offer_text']}")
                print(f"💰 Rebate: {sponsors[0]['rebate_amount']} {sponsors[0]['rebate_asset']}")
            
            print("\n✨ Done.")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(main())
