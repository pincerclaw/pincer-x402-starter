"""x402 Facilitator implementation for Pincer.

Pincer acts as its own x402 facilitator, verifying and settling payments
on-chain for both EVM (Base Sepolia) and SVM (Solana Devnet) networks.

Based on: https://github.com/coinbase/x402/blob/main/examples/python/facilitator/basic/main.py
"""

import sys
from pathlib import Path
from typing import Optional

from solders.keypair import Keypair

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.logging_utils import get_logger
from src.models import PaymentVerificationRequest, PaymentVerificationResponse
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

        # Initialize EVM signer if treasury key is configured
        if config.treasury_evm_private_key and config.treasury_evm_private_key.strip():
            try:
                evm_rpc_url = config.evm_rpc_url
                evm_signer = FacilitatorWeb3Signer(
                    private_key=config.treasury_evm_private_key,
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

        # Initialize SVM signer if treasury key is configured
        if config.treasury_svm_private_key and config.treasury_svm_private_key.strip():
            try:
                svm_keypair = Keypair.from_base58_string(config.treasury_svm_private_key)
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
                return PaymentVerificationResponse(
                    verified=True,
                    session_id=request.session_id,
                    user_address=response.payer,
                    network=str(requirements.network) if requirements.network else EVM_NETWORK,
                    amount_usd=config.content_price_usd,
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
