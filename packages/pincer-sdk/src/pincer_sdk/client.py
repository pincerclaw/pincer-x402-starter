"""Core Pincer Client."""

from typing import Any, Dict, Optional

import httpx

from .facilitator import PincerFacilitatorClient
from .merchant_utils import report_conversion_logic


class PincerClient:
    """Main entry point for Pincer SDK."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ):
        """Initialize Pincer Client.

        Args:
            base_url: The URL of the Pincer service.
            api_key: Optional API key for authentication.
            webhook_secret: Optional secret for signing webhooks (required for merchants).
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        
        # Initialize async HTTP client
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self):
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def facilitator(self) -> PincerFacilitatorClient:
        """Get a Pincer-specific facilitator for x402."""
        return PincerFacilitatorClient(self)

    async def report_conversion(
        self,
        session_id: str,
        user_address: str,
        purchase_amount: float,
        purchase_asset: str = "USD",
        merchant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Report a successful conversion to Pincer."""
        return await report_conversion_logic(
            self,
            session_id=session_id,
            user_address=user_address,
            purchase_amount=purchase_amount,
            purchase_asset=purchase_asset,
            merchant_id=merchant_id,
            details=details,
        )
