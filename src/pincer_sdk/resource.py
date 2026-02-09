"""Resource functionality for Pincer SDK."""

import logging
from typing import List, TYPE_CHECKING, Optional, Any
from contextvars import ContextVar

from .types import SponsoredOffer
from .facilitator import verification_var, PincerFacilitatorClient

if TYPE_CHECKING:
    from .client import PincerClient
    try:
        from x402.server import x402ResourceServer
    except ImportError:
        x402ResourceServer = Any

logger = logging.getLogger(__name__)



class ResourceClient:
    """Handles resource-specific interactions with Pincer."""

    def __init__(self, client: "PincerClient"):
        self.client = client

    async def get_sponsors(self, session_id: str) -> List[SponsoredOffer]:
        """Fetch active sponsor offers for the given session.

        Args:
            session_id: The session ID of the current user.

        Returns:
            List of SponsoredOffer objects.
        """
        try:
            response = await self.client._http.get(f"/sponsors/{session_id}")
            
            if response.status_code == 200:
                data = response.json()
                sponsors_data = data.get("sponsors", [])
                return [SponsoredOffer(**s) for s in sponsors_data]
            else:
                logger.warning(
                    f"Failed to fetch sponsors: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            logger.error(f"Error fetching sponsors: {e}", exc_info=True)
            return []

    def get_active_sponsors(self) -> List[SponsoredOffer]:
        """Get active sponsor offers for the current request context.
        
        This method retrieves sponsors that were verified by the Pincer facilitator
        during the x402 payment flow. It relies on the request context being active.
        
        Returns:
            List of SponsoredOffer objects.
        """
        verification_data = verification_var.get()
        if not verification_data:
            return []
            
        if hasattr(verification_data, "sponsors"):
            # Ensure we return a list of SponsoredOffer objects
            sponsors = []
            for s in verification_data.sponsors:
                if isinstance(s, SponsoredOffer):
                    sponsors.append(s)
                elif isinstance(s, dict):
                    try:
                        sponsors.append(SponsoredOffer(**s))
                    except Exception as e:
                        logger.warning(f"Failed to parse sponsor offer: {e}")
                else:
                    # Best effort conversion
                    try:
                        sponsors.append(SponsoredOffer(**dict(s)))
                    except Exception:
                        pass
            return sponsors
            
        return []

    def create_x402_server(self) -> "x402ResourceServer":
        """Create a pre-configured x402ResourceServer.
        
        Requires the x402 library to be installed.

        Returns:
            Configured x402ResourceServer instance.
        """
        try:
            from x402.server import x402ResourceServer
            from pydantic import BaseModel
        except ImportError:
            raise ImportError(
                "The 'x402' library is required to use create_x402_server. "
                "Please install it using 'pip install x402'."
            )

        # Custom Facilitator Client to preserve Pincer-specific data (sponsors, session_id)
        # Bypasses the default HTTPFacilitatorClient which strips extra fields
        
        facilitator = PincerFacilitatorClient(self.client)
        
        # Subclass x402ResourceServer to attach sponsors to the result
        if TYPE_CHECKING:
             from x402.server import x402ResourceServer
             return x402ResourceServer(facilitator) # type: ignore
        
        # Use standard x402ResourceServer with our custom facilitator
        # The Custom Facilitator handles capturing the 'sponsors' data into the ContextVar
        return x402ResourceServer(facilitator)



