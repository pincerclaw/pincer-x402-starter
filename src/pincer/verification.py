"""x402 Facilitator implementation for Pincer.

Pincer acts as its own x402 facilitator, verifying and settling payments
on-chain for both EVM (Base Sepolia) and SVM (Solana Devnet) networks.

Based on: https://github.com/coinbase/x402/blob/main/examples/python/facilitator/basic/main.py
"""

import sys
import uuid
from pathlib import Path
from typing import Optional

from eth_account import Account
from solders.keypair import Keypair

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.database import db
from src.logging_utils import get_logger
from src.models import (
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PaymentSession,
    SponsoredOffer,
)
from src.logging_utils import get_correlation_id
from datetime import datetime
from x402 import x402Facilitator
from x402.mechanisms.evm import FacilitatorWeb3Signer
from x402.mechanisms.evm.exact import register_exact_evm_facilitator
from x402.mechanisms.svm import FacilitatorKeypairSigner
from x402.mechanisms.svm.exact import register_exact_svm_facilitator
from x402.schemas import Network, PaymentRequirements, parse_payment_payload

logger = get_logger(__name__)

# Type definitions
EVM_NETWORK: Network = config.evm_network  # type: ignore
SVM_NETWORK: Network = config.svm_network  # type: ignore


class PincerFacilitator:
    """Pincer x402 Facilitator.

    Pincer IS the facilitator - it directly verifies and settles payments
    on-chain using treasury keys, instead of delegating to an external service.
    """

    def __init__(self):
        """Initialize the Pincer facilitator with EVM and SVM support."""
        logger.info("Initializing Pincer as x402 Facilitator...")

        # Async hook functions for observability
        async def before_verify_hook(ctx):
            logger.debug(f"Before verify: {ctx.payment_payload}")

        async def after_verify_hook(ctx):
            logger.debug(f"After verify: {ctx.result}")

        async def verify_failure_hook(ctx):
            logger.error(f"Verify failure: {ctx.error}")

        async def before_settle_hook(ctx):
            logger.info(f"Before settle: {ctx.payment_payload}")

        async def after_settle_hook(ctx):
            logger.info(f"After settle: {ctx.result}")

        async def settle_failure_hook(ctx):
            logger.error(f"Settle failure: {ctx.error}")

        # Initialize the x402 Facilitator with hooks
        self.facilitator = (
            x402Facilitator()
            .on_before_verify(before_verify_hook)
            .on_after_verify(after_verify_hook)
            .on_verify_failure(verify_failure_hook)
            .on_before_settle(before_settle_hook)
            .on_after_settle(after_settle_hook)
            .on_settle_failure(settle_failure_hook)
        )

        # Track which networks are configured
        evm_configured = False
        svm_configured = False

        # Initialize EVM signer
        evm_key = config.treasury_evm_private_key
        if not evm_key or not evm_key.strip():
            logger.warning("TREASURY_EVM_PRIVATE_KEY not set - generating temporary key for demo")
            evm_key = Account.create().key.hex()

        try:
            evm_rpc_url = config.evm_rpc_url
            evm_signer = FacilitatorWeb3Signer(
                private_key=evm_key,
                rpc_url=evm_rpc_url,
            )
            logger.info(f"EVM Facilitator account: {evm_signer.get_addresses()[0]}")

            register_exact_evm_facilitator(
                self.facilitator,
                evm_signer,
                networks=EVM_NETWORK,
                deploy_erc4337_with_eip6492=True,
            )
            logger.info(f"Registered EVM scheme for {EVM_NETWORK}")
            evm_configured = True
        except Exception as e:
            logger.warning(f"Failed to initialize EVM signer: {e}")

        # Initialize SVM signer
        svm_key = config.treasury_svm_private_key
        if not svm_key or not svm_key.strip():
            logger.warning("TREASURY_SVM_PRIVATE_KEY not set - generating temporary key for demo")
            svm_keypair = Keypair()
        else:
            svm_keypair = Keypair.from_base58_string(svm_key)

        try:
            svm_signer = FacilitatorKeypairSigner(svm_keypair)
            logger.info(f"SVM Facilitator account: {svm_signer.get_addresses()[0]}")

            register_exact_svm_facilitator(
                self.facilitator,
                svm_signer,
                networks=SVM_NETWORK,
            )
            logger.info(f"Registered SVM scheme for {SVM_NETWORK}")
            svm_configured = True
        except Exception as e:
            logger.warning(f"Failed to initialize SVM signer: {e}")

        # Warn if no networks are configured
        if not evm_configured and not svm_configured:
            logger.warning(
                "No facilitator signers configured! "
                "Set TREASURY_EVM_PRIVATE_KEY or TREASURY_SVM_PRIVATE_KEY to enable payment processing."
            )

        logger.info("Pincer Facilitator initialized")

    async def verify_payment(
        self, request: PaymentVerificationRequest
    ) -> PaymentVerificationResponse:
        """Verify an x402 payment.

        This method ONLY verifies payment validity. It does not:
        - Generate offers
        - Check sponsor budgets
        - Record sessions

        Sponsorship logic happens separately after verification succeeds.

        Args:
            request: Payment verification request.

        Returns:
            Payment verification response.
        """
        try:
            logger.info(f"Verifying payment for session {request.session_id}")

            # Parse payload and requirements
            payload = parse_payment_payload(request.payment_payload)
            requirements = PaymentRequirements.model_validate(request.payment_requirements)

            # Verify payment using the facilitator
            response = await self.facilitator.verify(payload, requirements)

            if response.is_valid:
                logger.info(f"Payment verified for session {request.session_id}, payer: {response.payer}")
                
                # Record session in DB to enable webhook processing
                try:
                     # Extract amount and asset from requirements if available, otherwise defaults
                     amount_paid = config.content_price_usd
                     payment_asset = "USDC" # or from config
                     
                     # MVP: Use config price directly
                     
                     session_record = PaymentSession(
                        session_id=request.session_id,
                        user_address=response.payer,
                        network=str(requirements.network) if requirements.network else str(EVM_NETWORK),
                        amount_paid=amount_paid,
                        payment_asset=payment_asset,
                        payment_hash=str(uuid.uuid4()), # We don't have the hash easily here without digging into payload
                        verified_at=datetime.utcnow(),
                        rebate_settled=False,
                        correlation_id=get_correlation_id(),
                    )
                     await db.create_session(session_record)
                     logger.info(f"Session recorded in DB: {request.session_id}")
                except Exception as e:
                    logger.error(f"Failed to record session in DB: {e}")
                    # Should we fail verification if DB save fails? 
                    # Yes, because otherwise webhook will fail later.
                    return PaymentVerificationResponse(
                        verified=False,
                        session_id=request.session_id,
                        error="Internal error: could not record session",
                    )
                
                # Check for active sponsor campaign (MVP: hardcoded check)
                sponsors = []
                try:
                    # MVP: In a real system, we'd select based on user profile/context
                    # Get active campaigns from DB (MVP: just take the first one)
                    campaigns = await db.get_active_campaigns()
                    if campaigns:
                        campaign = campaigns[0]
                    else:
                        campaign = None
                    
                    if campaign and campaign.active and campaign.budget_remaining >= campaign.rebate_amount:
                        # Generate unique offer ID
                        offer_id = f"off-{uuid.uuid4().hex[:8]}"
                        
                        # Determine rebate network based on payment or use campaign default
                        rebate_network = str(requirements.network) if requirements.network else campaign.rebate_network
                        
                        # Create sponsored offer with trackable checkout URL
                        offer = SponsoredOffer(
                            sponsor_id=campaign.campaign_id,
                            merchant_name=campaign.merchant_name,
                            offer_text=campaign.offer_text,
                            rebate_amount=campaign.rebate_amount,
                            rebate_asset=campaign.rebate_asset,
                            rebate_network=rebate_network,
                            coupons=campaign.coupons or [],
                            checkout_url=f"{config.merchant_url}/checkout?session_id={request.session_id}&offer_id={offer_id}",
                            session_id=request.session_id,
                            offer_id=offer_id,
                        )
                        sponsors.append(offer)
                        logger.info(f"Injected sponsor offer: {offer.offer_id}")
                except Exception as e:
                    logger.error(f"Failed to inject sponsor offer: {e}")
                    # Don't fail verification if offer injection fails
                
                return PaymentVerificationResponse(
                    verified=True,
                    session_id=request.session_id,
                    user_address=response.payer,
                    network=str(requirements.network) if requirements.network else EVM_NETWORK,
                    amount=config.content_price_usd,
                    sponsors=sponsors,
                )
            else:
                logger.warning(f"Payment verification failed: {response.invalid_reason}")
                return PaymentVerificationResponse(
                    verified=False,
                    session_id=request.session_id,
                    error=response.invalid_reason,
                )

        except Exception as e:
            logger.error(f"Payment verification failed: {e}", exc_info=True)
            return PaymentVerificationResponse(
                verified=False,
                session_id=request.session_id,
                error=str(e),
            )

    async def settle_payment(self, payment_payload: dict, payment_requirements: dict) -> dict:
        """Settle an x402 payment on-chain.

        Args:
            payment_payload: The payment payload.
            payment_requirements: The payment requirements.

        Returns:
            Settlement result with transaction details.
        """
        try:
            logger.info("Settling payment on-chain")

            # Parse payload and requirements
            payload = parse_payment_payload(payment_payload)
            requirements = PaymentRequirements.model_validate(payment_requirements)

            # Settle payment
            response = await self.facilitator.settle(payload, requirements)

            return {
                "success": response.success,
                "transaction": response.transaction,
                "network": response.network,
                "payer": response.payer,
                "errorReason": response.error_reason,
            }

        except Exception as e:
            logger.error(f"Payment settlement failed: {e}", exc_info=True)

            # Check if this was an abort from hook
            if "aborted" in str(e).lower():
                return {
                    "success": False,
                    "errorReason": str(e),
                    "network": payment_payload.get("accepted", {}).get("network", "unknown"),
                    "transaction": "",
                }

            raise

    def get_supported(self) -> dict:
        """Get supported payment kinds and extensions.

        Returns:
            Supported payment capabilities.
        """
        response = self.facilitator.get_supported()

        return {
            "kinds": [
                {
                    "x402Version": k.x402_version,
                    "scheme": k.scheme,
                    "network": k.network,
                    "extra": k.extra,
                }
                for k in response.kinds
            ],
            "extensions": response.extensions,
            "signers": response.signers,
        }


# Global facilitator instance
pincer_facilitator = PincerFacilitator()

# Backwards compatibility alias
verifier = pincer_facilitator
