"""Core Pincer Client."""

import httpx
from typing import Optional

from .merchant import MerchantClient
from .resource import ResourceClient


class PincerClient:
    """Main entry point for Pincer SDK."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
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

    @property
    def merchant(self) -> MerchantClient:
        """Access merchant-specific functionality."""
        return MerchantClient(self)

    @property
    def resource(self) -> ResourceClient:
        """Access resource-specific functionality."""
        return ResourceClient(self)
