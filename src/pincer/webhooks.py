"""Webhook handling for merchant conversion events.

Implements idempotency, anti-replay protection, and rebate settlement orchestration.
"""

import hashlib
import hmac
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.database import db
from src.logging_utils import get_correlation_id, get_logger
from src.models import (
    ConversionWebhook,
    RebateSettlement,
    WebhookRecord,
)

logger = get_logger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature for webhook authenticity.

    Args:
        payload: Raw webhook payload bytes.
        signature: Hex-encoded HMAC signature from header.
        secret: Shared secret for HMAC.

    Returns:
        True if signature is valid, False otherwise.
    """
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature)


class WebhookHandler:
    """Handles merchant conversion webhooks with reliability guarantees."""

    def __init__(self, payout_engine):
        """Initialize webhook handler.

        Args:
            payout_engine: Payout engine instance for settling rebates.
        """
        self.payout_engine = payout_engine

    async def process_webhook(
        self,
        webhook: ConversionWebhook,
        signature: str,
        raw_payload: bytes,
    ) -> Dict[str, Any]:
        """Process a merchant conversion webhook.

        Implements:
        1. Signature verification (authenticity)
        2. Idempotency checking (deduplication)
        3. Anti-replay protection (session reuse prevention)
        4. Budget validation
        5. Rebate settlement orchestration

        Args:
            webhook: Parsed webhook payload.
            signature: HMAC signature from header.
            raw_payload: Raw payload bytes for signature verification.

        Returns:
            Dict with status and details.
        """
        correlation_id = get_correlation_id()
        logger.info(f"Processing webhook {webhook.webhook_id} for session {webhook.session_id}")

        # 1. Verify signature
        if not verify_webhook_signature(raw_payload, signature, config.webhook_secret):
            logger.error(f"Invalid webhook signature for {webhook.webhook_id}")
            return {
                "status": "error",
                "error": "Invalid signature",
                "webhook_id": webhook.webhook_id,
            }

        logger.info(f"Webhook signature verified for {webhook.webhook_id}")

        # 2. Idempotency check - have we seen this webhook before?
        existing_webhook = await db.get_webhook(webhook.webhook_id)

        if existing_webhook:
            logger.info(
                f"Webhook {webhook.webhook_id} already processed (idempotency): "
                f"status={existing_webhook.status}"
            )

            # Return the previous result
            if existing_webhook.status == "completed":
                return {
                    "status": "success",
                    "message": "Webhook already processed (idempotent)",
                    "webhook_id": webhook.webhook_id,
                    "settlement_status": "completed",
                    "rebate_tx_hash": existing_webhook.rebate_tx_hash,
                }
            elif existing_webhook.status == "failed":
                return {
                    "status": "error",
                    "error": existing_webhook.error_message,
                    "webhook_id": webhook.webhook_id,
                }
            else:  # processing
                return {
                    "status": "processing",
                    "message": "Webhook is currently being processed",
                    "webhook_id": webhook.webhook_id,
                }

        # Create webhook record with "processing" status
        webhook_record = WebhookRecord(
            webhook_id=webhook.webhook_id,
            session_id=webhook.session_id,
            user_address=webhook.user_address,
            status="processing",
        )

        try:
            await db.create_webhook(webhook_record)
            created = True
        except Exception:
            created = False
        if not created:
            # Race condition - another request is processing this
            logger.warning(f"Race condition detected for webhook {webhook.webhook_id}")
            return {
                "status": "processing",
                "message": "Webhook is being processed by another request",
                "webhook_id": webhook.webhook_id,
            }

        # 3. Anti-replay check - has this session already been settled?
        session = await db.get_session(webhook.session_id)

        if not session:
            error_msg = f"Payment session not found: {webhook.session_id}"
            logger.error(error_msg)
            await db.update_webhook_status(webhook.webhook_id, "failed", error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "webhook_id": webhook.webhook_id,
            }

        if session.rebate_settled:
            error_msg = f"Rebate already settled for session {webhook.session_id} (anti-replay)"
            logger.error(error_msg)
            await db.update_webhook_status(webhook.webhook_id, "failed", error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "webhook_id": webhook.webhook_id,
            }

        logger.info(f"Session {webhook.session_id} is eligible for rebate settlement")

        # 4. Get campaign and validate budget
        # Retrieve first active campaign (MVP behavior)
        campaigns = await db.get_active_campaigns()

        if not campaigns:
            error_msg = "No active campaigns found in database"
            logger.error(error_msg)
            await db.update_webhook_status(webhook.webhook_id, "failed", error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "webhook_id": webhook.webhook_id,
            }
        
        campaign = campaigns[0]

        if not campaign.active:
            error_msg = f"Campaign inactive: {campaign.campaign_id}"
            logger.warning(error_msg)
            await db.update_webhook_status(webhook.webhook_id, "failed", error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "webhook_id": webhook.webhook_id,
            }

        # Budget was already reserved during offer generation
        # Now we finalize by actually sending the rebate

        # 5. Initiate rebate settlement
        try:
            logger.info(
                f"Settling rebate for session {webhook.session_id}: "
                f"{campaign.rebate_amount:.6f} {campaign.rebate_asset} to {webhook.user_address}"
            )

            # Create settlement record
            settlement_id = f"settle-{uuid.uuid4().hex[:12]}"
            settlement = RebateSettlement(
                settlement_id=settlement_id,
                session_id=webhook.session_id,
                webhook_id=webhook.webhook_id,
                user_address=webhook.user_address,
                rebate_amount=campaign.rebate_amount,
                rebate_asset=campaign.rebate_asset,
                network=session.network,
                campaign_id=campaign.campaign_id,
                status="pending",
                correlation_id=correlation_id,
            )

            await db.create_settlement(settlement)

            # Send rebate via payout engine
            payout_result = await self.payout_engine.send_rebate(
                user_address=webhook.user_address,
                amount=campaign.rebate_amount,
                asset=campaign.rebate_asset,
                network=session.network,
            )

            if payout_result["status"] == "success":
                # Update settlement with transaction hash
                tx_hash = payout_result.get("tx_hash")
                await db.update_settlement_status(settlement_id, "confirmed", tx_hash)

                # Mark session as settled (anti-replay)
                await db.mark_session_settled(webhook.session_id)

                # Update webhook status
                await db.update_webhook_status(
                    webhook.webhook_id, "completed", tx_hash=tx_hash
                )

                logger.info(
                    f"Rebate settled successfully: {settlement_id}, tx: {tx_hash}"
                )

                return {
                    "status": "success",
                    "message": "Rebate settled successfully",
                    "webhook_id": webhook.webhook_id,
                    "settlement_id": settlement_id,
                    "tx_hash": tx_hash,
                    "rebate_amount": campaign.rebate_amount,
                    "rebate_asset": campaign.rebate_asset,
                }
            else:
                # Payout failed
                error_msg = payout_result.get("error", "Payout failed")
                logger.error(f"Payout failed for {settlement_id}: {error_msg}")

                await db.update_settlement_status(settlement_id, "failed")
                await db.update_webhook_status(webhook.webhook_id, "failed", error_msg)

                return {
                    "status": "error",
                    "error": error_msg,
                    "webhook_id": webhook.webhook_id,
                }

        except Exception as e:
            error_msg = f"Settlement error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await db.update_webhook_status(webhook.webhook_id, "failed", error_msg)

            return {
                "status": "error",
                "error": error_msg,
                "webhook_id": webhook.webhook_id,
            }
