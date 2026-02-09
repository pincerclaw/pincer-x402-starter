"""Merchant functionality for Pincer SDK."""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING

from .types import ConversionResponse
from .utils import create_webhook_signature

if TYPE_CHECKING:
    from .client import PincerClient

logger = logging.getLogger(__name__)


class MerchantClient:
    """Handles merchant-specific interactions with Pincer."""

    def __init__(self, client: "PincerClient"):
        self.client = client

    async def report_conversion(
        self,
        session_id: str,
        user_address: str,
        purchase_amount: float,
        purchase_asset: str = "USD",
        merchant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ConversionResponse:
        """Report a successful conversion to Pincer.

        Args:
            session_id: The session ID associated with the user's visit.
            user_address: The wallet address of the user who made the purchase.
            purchase_amount: The value of the purchase.
            purchase_asset: The currency of the purchase (default: USD).
            merchant_id: Optional merchant identifier.
            details: Optional extra details about the conversion.

        Returns:
            ConversionResponse object indicating success or failure.
        """
        if not self.client.webhook_secret:
            raise ValueError("webhook_secret is required to report conversions")

        webhook_id = f"wh-{uuid.uuid4().hex[:12]}"
        
        # Construct payload
        payload = {
            "webhook_id": webhook_id,
            "session_id": session_id,
            "user_address": user_address,
            "purchase_amount": purchase_amount,
            "purchase_asset": purchase_asset,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "merchant_id": merchant_id or "unknown-merchant",
        }
        
        if details:
            payload.update(details)

        # Create JSON string for signing
        payload_str = json.dumps(payload)
        
        # Generate signature
        signature = create_webhook_signature(payload_str, self.client.webhook_secret)

        logger.info(f"Reporting conversion {webhook_id} to Pincer for session {session_id}")

        try:
            response = await self.client._http.post(
                "/webhooks/conversion",
                content=payload_str,
                headers={
                    "X-Webhook-Signature": signature,
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return ConversionResponse(
                    status="success",
                    webhook_id=webhook_id,
                    message=data.get("status", "Conversion reported successfully"),
                )
            else:
                error_msg = f"Failed to report conversion: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return ConversionResponse(
                    status="error",
                    webhook_id=webhook_id,
                    error=error_msg,
                )

        except Exception as e:
            logger.error(f"Error reporting conversion: {e}", exc_info=True)
            return ConversionResponse(
                status="error",
                webhook_id=webhook_id,
                error=str(e),
            )

    def create_x402_server(self) -> Any:
        """Create a pre-configured x402ResourceServer.
        
        Proxy for client.resource.create_x402_server to unify the API.
        """
        return self.client.resource.create_x402_server()

    def get_active_sponsors(self) -> Any:
        """Get active sponsor offers for the current request context.
        
        Proxy for client.resource.get_active_sponsors.
        """
        return self.client.resource.get_active_sponsors()
