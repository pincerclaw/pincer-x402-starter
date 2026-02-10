"""Sponsor Conversion Reporting Script.

Simulates a merchant backend reporting a conversion to Pincer.
No server required - just a direct API call.

Usage:
    uv run python examples/sponsor_integration.py [session_id]
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

from pincer_sdk import PincerClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

PINCER_URL = os.getenv("PINCER_URL", "https://pincer.zeabur.app")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or os.getenv("SPONSOR_WEBHOOK_SECRET")

async def report_conversion(session_id: str):
    print(f"🚀 Reporting Conversion to {PINCER_URL}")
    print(f"   Session ID: {session_id}")
    
    if not WEBHOOK_SECRET:
        print("❌ Error: WEBHOOK_SECRET not set in .env")
        return

    # Initialize Pincer Client
    async with PincerClient(base_url=PINCER_URL, webhook_secret=WEBHOOK_SECRET) as pincer:
        try:
            # Simulate a purchase
            user_address = "SimulatedUserAddress" 
            amount = 25.00
            
            print(f"   Reporting purchase of ${amount}...")
            
            result = await pincer.report_conversion(
                session_id=session_id,
                user_address=user_address,
                purchase_amount=amount,
                purchase_asset="USD",
                merchant_id="example-merchant"
            )
            
            if result.status == "success":
                print(f"✅ Conversion Success! Rebate Triggered.")
                print(f"   Webhook ID: {result.webhook_id}")
            else:
                print(f"⚠️ Reporting Failed: {result.error}")
                print(f"   Message: {result.message}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Get session ID from args or prompt
    if len(sys.argv) > 1:
        sid = sys.argv[1]
    else:
        print("💡 Tip: You can pass session_id as an argument")
        sid = input("Enter Session ID to report: ").strip()

    if sid:
        asyncio.run(report_conversion(sid))
    else:
        print("❌ No session ID provided.")
