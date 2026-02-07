"""Agent Demo Script - End-to-End Pincer x402 Flow.

Demonstrates:
Phase A: Paywalled content access (user pays first)
Phase B: Offer selection  
Phase C: Merchant conversion and rebate

Based on Coinbase x402 httpx client example.
"""

import asyncio
import sys
from pathlib import Path

import httpx
from eth_account import Account

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config, validate_config_for_service
from src.logging_utils import (
    CorrelationIdContext,
    generate_correlation_id,
    get_logger,
    setup_logging,
)
from x402 import x402Client
from x402.http import x402HTTPClient
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client

# Validate configuration
validate_config_for_service("agent")

# Setup logging
setup_logging(config.log_level, "text")  # Use text format for better readability in demo
logger = get_logger(__name__)


def print_section(title: str):
    """Print a section header for demo output."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


async def main():
    """Run the end-to-end demo."""

    # Generate correlation ID for this demo run
    correlation_id = generate_correlation_id()

    with CorrelationIdContext(correlation_id):
        print_section("🚀 Pincer x402 Demo - Post-Pay Rebate Flow")
        logger.info(f"Starting demo with correlation ID: {correlation_id}")

        # ====================================================================
        # PHASE A: Paywalled Content Access
        # ====================================================================
        print_section("Phase A: Requesting Premium Content from TopEats")

        print("📍 Step 1: Initial request to /recommendations (no payment)\n")

        # Make initial request without payment
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.topeats_url}/recommendations",
                    headers={"X-Correlation-Id": correlation_id},
                )

                if response.status_code == 402:
                    print("✅ Received HTTP 402 Payment Required")
                    print(f"   Payment header: {response.headers.get('payment-required', 'N/A')[:100]}...")
                else:
                    print(f"❌ Unexpected status: {response.status_code}")
                    return

        except Exception as e:
            logger.error(f"Error making initial request: {e}")
            return

        print("\n📍 Step 2: User approves payment\n")
        print(f"   💰 Amount: ${config.content_price_usd}")
        print(f"   🔗 Networks: {config.svm_network} (優先) or {config.evm_network}")
        print("   ✅ Payment approved by user\n")

        print("📍 Step 3: Retry request with payment proof\n")

        # Create x402 client
        client = x402Client()
        http_client = x402HTTPClient(client)

        # Register payment schemes (優先使用 Solana)
        user_address = None
        network_used = None

        # 優先嘗試使用 Solana (SVM)
        if config.svm_private_key:
            svm_signer = KeypairSigner.from_base58(config.svm_private_key)
            register_exact_svm_client(client, svm_signer)
            user_address = svm_signer.address
            network_used = config.svm_network
            print(f"   💼 Using Solana account: {svm_signer.address}")
            print(f"   🌐 Network: Solana Devnet")
        # 次要：使用 EVM 作為備選
        elif config.evm_private_key:
            account = Account.from_key(config.evm_private_key)
            register_exact_evm_client(client, EthAccountSigner(account))
            user_address = account.address
            network_used = config.evm_network
            print(f"   💼 Using EVM account: {account.address}")
            print(f"   🌐 Network: Base Sepolia")
        else:
            print("❌ No private key configured!")
            print("   Please set SVM_PRIVATE_KEY (優先) or EVM_PRIVATE_KEY in .env")
            return

        # Make request with x402 client (automatically handles payment)
        async with x402HttpxClient(client) as http:
            response = await http.get(
                f"{config.topeats_url}/recommendations",
                headers={"X-Correlation-Id": correlation_id},
            )
            await response.aread()

            if response.is_success:
                print(f"\n✅ Payment verified! Received HTTP {response.status_code}")

                # Parse response
                data = response.json()
                restaurants = data.get("restaurants", [])
                sponsored_offers = data.get("sponsored_offers", [])
                session_id = data.get("session_id")

                print(f"\n📋 Received {len(restaurants)} restaurant recommendations")
                for i, restaurant in enumerate(restaurants[:3], 1):
                    print(f"   {i}. {restaurant['name']} - {restaurant['cuisine']} ({'$' * restaurant['price_level']})")

                # Extract payment response
                try:
                    settle_response = http_client.get_payment_settle_response(
                        lambda name: response.headers.get(name)
                    )
                    print(f"\n💳 Payment settled: {settle_response.model_dump_json(indent=2)[:200]}...")
                except ValueError:
                    print("\n💳 Payment completed (no settlement response in headers)")

                # ====================================================================
                # PHASE B: Sponsored Offers
                # ====================================================================
                if sponsored_offers:
                    print_section("Phase B: Sponsored Offers Received")

                    print(f"🎁 Received {len(sponsored_offers)} sponsored offer(s):\n")

                    for i, offer in enumerate(sponsored_offers, 1):
                        print(f"   Offer {i}:")
                        print(f"      Merchant: {offer['merchant_name']}")
                        print(f"      Offer: {offer['offer_text']}")
                        print(f"      Rebate: {offer['rebate_amount']}")
                        print(f"      Session ID: {offer['session_id']}")
                        print()

                    print("📍 User selects offer: Shake Shack\n")
                    selected_offer = sponsored_offers[0]

                    # ====================================================================
                    # PHASE C: Merchant Conversion and Rebate
                    # ====================================================================
                    print_section("Phase C: Merchant Purchase and Rebate Settlement")

                    print("📍 Step 1: User proceeds to merchant checkout\n")
                    print(f"   🍔 Merchant: {selected_offer['merchant_name']}")
                    print(f"   💰 Order amount: $25.00")
                    print(f"   🎟️  Session ID: {selected_offer['session_id']}\n")

                    # Simulate merchant checkout
                    async with httpx.AsyncClient() as merchant_client:
                        checkout_response = await merchant_client.post(
                            f"{config.merchant_url}/checkout",
                            json={
                                "session_id": selected_offer['session_id'],
                                "user_address": user_address,
                                "purchase_amount_usd": 25.00,
                            },
                            headers={"X-Correlation-Id": correlation_id},
                        )

                        if checkout_response.status_code == 200:
                            checkout_data = checkout_response.json()
                            print("✅ Checkout completed!")
                            print(f"   Order ID: {checkout_data['order_id']}")
                            print(f"   Webhook sent: {checkout_data['webhook_sent']}")
                            print(f"   Webhook ID: {checkout_data['webhook_id']}\n")

                            print("📍 Step 2: Waiting for rebate settlement...\n")
                            print("   ⏳ Pincer is processing the conversion webhook...")
                            print("   🔒 Verifying: idempotency, anti-replay, budget")
                            print("   💸 Initiating rebate transfer\n")

                            # Wait a moment for webhook processing
                            await asyncio.sleep(2)

                            print(f"✅ Rebate should be settled!")
                            print(f"   💵 Amount: {selected_offer['rebate_amount']}")
                            print(f"   👛 To: {user_address}")
                            print(f"   🔗 Network: {network_used}")
                            print("\n   Note: Check Pincer service logs for transaction hash")

                        else:
                            print(f"❌ Checkout failed: {checkout_response.status_code}")
                            print(checkout_response.text)

                else:
                    print("\n❌ No sponsored offers received")
                    print("   This might happen if campaign budget is exhausted")

            else:
                print(f"\n❌ Payment failed: HTTP {response.status_code}")
                print(response.text)

        # ====================================================================
        # Summary
        # ====================================================================
        print_section("✨ Demo Complete")
        print("End-to-end flow demonstrated:")
        print("  ✅ Phase A: x402 paywalled content access")
        print("  ✅ Phase B: Sponsored offer injection")
        print("  ✅ Phase C: Merchant conversion and rebate settlement")
        print(f"\n📊 Correlation ID: {correlation_id}")
        print("\nTo verify:")
        print("  1. Check logs across all services for this correlation ID")
        # Only show database query if payment succeeded
        if response.is_success and 'session_id' in locals():
            print("  2. Query database for settlement record:")
            print(f"     sqlite3 pincer.db \"SELECT * FROM settlements WHERE session_id='{session_id}';\"")
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
