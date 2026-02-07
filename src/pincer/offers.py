"""Offer generation engine for Pincer.

Generates sponsored offers after payment verification succeeds.
Handles budget checking and reservation.
"""

import sys
import uuid
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.database import db
from src.logging_utils import get_correlation_id, get_logger
from src.models import (
    OfferGenerationRequest,
    OfferGenerationResponse,
    PaymentSession,
    SponsoredOffer,
)

logger = get_logger(__name__)


class OfferEngine:
    """Generates sponsored offers for verified payment sessions."""

    async def generate_offers(
        self, request: OfferGenerationRequest
    ) -> OfferGenerationResponse:
        """Generate sponsored offers for a verified payment session.

        This should be called AFTER payment verification succeeds.
        It checks campaign budgets and reserves funds for offers.

        Args:
            request: Offer generation request with session details.

        Returns:
            Response containing generated offers.
        """
        correlation_id = request.correlation_id or get_correlation_id()
        logger.info(f"Generating offers for session {request.session_id}")

        offers = []

        try:
            # Record the payment session for anti-replay protection
            session = PaymentSession(
                session_id=request.session_id,
                user_address=request.user_address,
                network=request.network,
                amount_paid_usd=request.amount_paid_usd,
                payment_hash=None,  # Could extract from payment proof if needed
                rebate_settled=False,
                correlation_id=correlation_id,
            )
            await db.create_session(session)
            logger.info(f"Recorded payment session: {request.session_id}")

            # Get the default campaign (MVP: hardcoded single sponsor)
            campaign = await db.get_campaign(config.sponsor_campaign_id)

            if not campaign:
                logger.warning(f"Campaign not found: {config.sponsor_campaign_id}")
                return OfferGenerationResponse(offers=[], session_id=request.session_id)

            if not campaign.active:
                logger.info(f"Campaign inactive: {campaign.campaign_id}")
                return OfferGenerationResponse(offers=[], session_id=request.session_id)

            # Check if budget is sufficient for rebate
            if campaign.remaining_budget_usd < campaign.rebate_amount_usd:
                logger.warning(
                    f"Insufficient budget for campaign {campaign.campaign_id}: "
                    f"${campaign.remaining_budget_usd:.2f} remaining, "
                    f"${campaign.rebate_amount_usd:.2f} needed"
                )
                return OfferGenerationResponse(offers=[], session_id=request.session_id)

            # Reserve budget for this offer
            reserved = await db.reserve_budget(
                campaign.campaign_id, campaign.rebate_amount_usd
            )

            if not reserved:
                logger.warning(f"Failed to reserve budget for {campaign.campaign_id}")
                return OfferGenerationResponse(offers=[], session_id=request.session_id)

            # Generate the offer
            offer_id = f"offer-{uuid.uuid4().hex[:12]}"
            offer = SponsoredOffer(
                sponsor_id=campaign.campaign_id,
                merchant_name=campaign.merchant_name,
                offer_text=campaign.offer_text,
                rebate_amount=f"${campaign.rebate_amount_usd:.2f}",
                merchant_url=f"{config.merchant_url}/checkout",
                session_id=request.session_id,
                offer_id=offer_id,
            )

            offers.append(offer)
            logger.info(
                f"Generated offer {offer_id} for campaign {campaign.campaign_id}: "
                f"{campaign.merchant_name} - {campaign.offer_text}"
            )

        except Exception as e:
            logger.error(f"Error generating offers: {e}", exc_info=True)

        return OfferGenerationResponse(offers=offers, session_id=request.session_id)


# Global offer engine instance
offer_engine = OfferEngine()
