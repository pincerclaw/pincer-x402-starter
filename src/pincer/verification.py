"""x402 payment verification logic for Pincer.

Reuses Coinbase x402 SDK for actual verification while remaining neutral
to sponsorship concerns. Verification happens independently and first.
"""

import sys
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.logging_utils import get_logger
from src.models import PaymentVerificationRequest, PaymentVerificationResponse
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.mechanisms.svm.exact import ExactSvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

logger = get_logger(__name__)

# Type definitions
EVM_NETWORK: Network = config.evm_network  # type: ignore
SVM_NETWORK: Network = config.svm_network  # type: ignore


class PaymentVerifier:
    """x402 payment verification using Coinbase SDK.

    This class is deliberately separated from sponsorship logic.
    It only verifies that payments are valid per x402 protocol.
    """

    def __init__(self):
        """Initialize the payment verifier with x402 server."""
        logger.info("Initializing payment verifier...")

        # Create facilitator client (can delegate to public facilitator)
        facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=config.facilitator_url))

        # Create x402 resource server
        self.server = x402ResourceServer(facilitator)

        # Register payment schemes
        logger.info(f"Registering EVM scheme for {EVM_NETWORK}")
        self.server.register(EVM_NETWORK, ExactEvmServerScheme())

        logger.info(f"Registering SVM scheme for {SVM_NETWORK}")
        self.server.register(SVM_NETWORK, ExactSvmServerScheme())

        logger.info("Payment verifier initialized")

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

            # TODO: Implement actual verification using x402 SDK
            # For now, this is a placeholder that shows the separation of concerns
            #
            # In a full implementation, this would:
            # 1. Parse the payment signature
            # 2. Verify cryptographic signatures
            # 3. Check amounts match requirements
            # 4. Return verification result
            #
            # See Coinbase examples for full implementation details

            # Placeholder response
            logger.warning(
                "Payment verification is a placeholder - "
                "full x402 verification to be implemented"
            )

            return PaymentVerificationResponse(
                verified=True,
                session_id=request.session_id,
                user_address="placeholder_address",
                network=EVM_NETWORK,
                amount_usd=config.content_price_usd,
            )

        except Exception as e:
            logger.error(f"Payment verification failed: {e}", exc_info=True)
            return PaymentVerificationResponse(
                verified=False,
                session_id=request.session_id,
                error=str(e),
            )


# Global verifier instance
verifier = PaymentVerifier()
