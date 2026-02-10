"""Pincer x402 Demo - Payment-Gated API Access.

Demonstrates the complete x402 payment flow:
1. Request paywalled content → Receive HTTP 402
2. Sign and submit payment proof
3. Access content + receive sponsor offers

Based on Coinbase x402 httpx client example.
"""

import asyncio

import httpx
from eth_account import Account
from x402 import x402Client
from x402.http import x402HTTPClient
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client

from src.config import config, validate_config_for_service
from src.logging_utils import (
    CorrelationIdContext,
    generate_correlation_id,
    get_logger,
    setup_logging,
)

# Validate configuration
validate_config_for_service("agent")

# Setup logging
setup_logging(config.log_level, "text")  # Use text format for better readability in demo
logger = get_logger(__name__)


def print_header(title: str):
    """Print a section header for demo output."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_step(step: int, title: str):
    """Print a step indicator."""
    print(f"\n{'─' * 70}")
    print(f"  Step {step}: {title}")
    print(f"{'─' * 70}\n")


async def main():
    """Run the end-to-end demo."""

    # Generate correlation ID for this demo run
    correlation_id = generate_correlation_id()

    with CorrelationIdContext(correlation_id):
        print_header("🚀 Pincer x402 Demo")
        print("This demo shows how x402 enables payment-gated API access.")
        print(f"Correlation ID: {correlation_id}")
        logger.info(f"Starting demo with correlation ID: {correlation_id}")

        # ====================================================================
        # Step 1: Initial Request (No Payment)
        # ====================================================================
        print_step(1, "Request paywalled content (no payment)")

        print("Making GET request to /recommendations without payment...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.resource_url}/recommendations",
                    headers={"X-Correlation-Id": correlation_id},
                )

                if response.status_code == 402:
                    print("\n✅ Server returned HTTP 402 Payment Required")
                    print("   → This is expected! The endpoint requires payment.")
                else:
                    print(f"\n❌ Unexpected status: {response.status_code}")
                    return

        except Exception as e:
            logger.error(f"Error making initial request: {e}")
            return

        # ====================================================================
        # Step 2: Setup Payment
        # ====================================================================
        print_step(2, "Prepare payment credentials")

        # Format payment amount properly
        # Format payment amount properly
        price_usd = config.content_price_usd
        print(f"Payment amount: {price_usd:.6f} USDC")

        # Create x402 client
        client = x402Client()
        http_client = x402HTTPClient(client)

        # Register payment schemes (優先使用 Solana)
        _ = None
        network_name = None
        is_solana = False

        if config.svm_private_key:
            svm_signer = KeypairSigner.from_base58(config.svm_private_key)
            register_exact_svm_client(client, svm_signer)
            _ = svm_signer.address
            network_name = "Solana Devnet"
            is_solana = True
            print(f"\n🔐 Wallet: {svm_signer.address}")
            print(f"   → https://solscan.io/account/{svm_signer.address}?cluster=devnet")
            print(f"🌐 Network: {network_name}")
        elif config.evm_private_key:
            account = Account.from_key(config.evm_private_key)
            register_exact_evm_client(client, EthAccountSigner(account))
            _ = account.address
            network_name = "Base Sepolia"
            is_solana = False
            print(f"\n🔐 Wallet: {account.address}")
            print(f"   → https://sepolia.basescan.org/address/{account.address}")
            print(f"🌐 Network: {network_name}")
        else:
            print("\n❌ No private key configured!")
            print("   Set SVM_PRIVATE_KEY or EVM_PRIVATE_KEY in .env")
            return

        # ====================================================================
        # Step 3: Request with Payment
        # ====================================================================
        print_step(3, "Request with payment proof")

        print("Signing payment and retrying request...")
        print("(x402 client handles this automatically)")

        async with x402HttpxClient(client) as http:
            response = await http.get(
                f"{config.resource_url}/recommendations",
                headers={"X-Correlation-Id": correlation_id},
            )
            await response.aread()

            if response.is_success:
                print(f"\n✅ Success! HTTP {response.status_code}")

                # Parse response
                data = response.json()
                restaurants = data.get("restaurants", [])
                session_id = data.get("session_id")

                # ====================================================================
                # Step 4: Display Results
                # ====================================================================
                print_step(4, "Content received")

                print(f"📋 {len(restaurants)} restaurant recommendations:\n")
                for i, restaurant in enumerate(restaurants[:5], 1):
                    _ = "⭐" * int(restaurant.get('rating', 0))
                    price = "$" * restaurant['price_level']
                    print(f"   {i}. {restaurant['name']}")
                    print(f"      {restaurant['cuisine']} | {price} | {restaurant.get('rating', 'N/A')}★")
                    if restaurant.get('description'):
                        print(f"      \"{restaurant['description'][:50]}...\"")
                    print()

                # Print sponsors if available
                sponsors = data.get("sponsors", [])
                if sponsors:
                    print("\n🎁 Sponsor Offers:\n")
                    for sponsor in sponsors:
                        print(f"   💰 {sponsor['merchant_name']}")
                        print(f"      {sponsor['offer_text']}")
                        # Handle rebate amount which might be string (old) or float (new)
                        rebate_val = sponsor.get('rebate_amount')
                        rebate_asset = sponsor.get('rebate_asset', 'USDC')
                        if isinstance(rebate_val, float):
                            print(f"      Rebate: {rebate_val:.6f} {rebate_asset} (x402 fee refund)")
                        else:
                            print(f"      Rebate: {rebate_val} (x402 fee refund)")
                        
                        # Display coupons
                        coupons = sponsor.get('coupons', [])
                        if coupons:
                            print("      Coupons:")
                            for coupon in coupons:
                                discount = f"{coupon['discount_value']}%" if coupon['discount_type'] == 'percentage' else f"${coupon['discount_value']}"
                                print(f"         • {coupon['code']}: {coupon['description']} ({discount})")
                        
                        # Display checkout URL
                        if 'checkout_url' in sponsor:
                            print(f"      Checkout: {sponsor['checkout_url']}")
                        elif 'merchant_url' in sponsor:
                            print(f"      Checkout: {sponsor['merchant_url']}")
                        print()
                else:
                    print("\n🎁 Sponsor Offers: None available for this session.\n")

                # Extract payment response
                try:
                    settle_response = http_client.get_payment_settle_response(
                        lambda name: response.headers.get(name)
                    )
                    print("\n💳 Payment Settlement:")
                    print(f"   Status: {'✅ Success' if settle_response.success else '❌ Failed'}")
                    print(f"   Payer: {settle_response.payer}")
                    if settle_response.transaction:
                        tx = settle_response.transaction
                        print(f"   TX: {tx}")
                        # Add explorer link
                        if is_solana:
                            print(f"   → https://solscan.io/tx/{tx}?cluster=devnet")
                        else:
                            print(f"   → https://sepolia.basescan.org/tx/{tx}")
                except ValueError:
                    print("\n💳 Payment completed")

            else:
                print(f"\n❌ Request failed: HTTP {response.status_code}")
                print(response.text)
                return

        # ====================================================================
        # Summary
        # ====================================================================
        print_header("✨ Demo Complete")
        
        print("What happened:")
        print("  1. Initial request returned HTTP 402 (Payment Required)")
        print("  2. x402 client signed a payment transaction")
        print("  3. Pincer (facilitator) verified the payment on-chain")
        print("  4. Content + sponsor offers returned to user")
        print()
        print(f"Session ID: {session_id}")
        print(f"Correlation ID: {correlation_id}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
