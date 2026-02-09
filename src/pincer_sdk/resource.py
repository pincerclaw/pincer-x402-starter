"""Resource functionality for Pincer SDK."""

import logging
from typing import List, TYPE_CHECKING, Optional, Any
from contextvars import ContextVar

from .types import SponsoredOffer

if TYPE_CHECKING:
    from .client import PincerClient
    try:
        from x402.server import x402ResourceServer
    except ImportError:
        x402ResourceServer = Any

logger = logging.getLogger(__name__)

# Context variable to store verification result for the current request
verification_var: ContextVar[Optional[Any]] = ContextVar("verification_result", default=None)


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
        class PincerVerificationResponse(BaseModel):
            is_valid: bool
            invalid_reason: Optional[str] = None
            payer: Optional[str] = None
            sponsors: List[SponsoredOffer] = []
            
            model_config = {"extra": "allow"}

        class PincerFacilitatorClient:
            def __init__(self, client):
                self.client = client

            async def verify(self, payload, requirements):
                # payload is PaymentPayload, requirements is PaymentRequirements
                
                # Serialize payload and requirements for Pincer API
                # Handle both Pydantic v2 (model_dump) and v1 (dict) or plain dicts
                # IMPORTANT: Use by_alias=True to preserve camelCase field names required by x402 protocol
                if hasattr(payload, "model_dump"):
                    p_dict = payload.model_dump(by_alias=True, mode='json')
                elif hasattr(payload, "dict"):
                    p_dict = payload.dict(by_alias=True)
                else:
                    p_dict = payload

                if hasattr(requirements, "model_dump"):
                    r_dict = requirements.model_dump(by_alias=True, mode='json')
                elif hasattr(requirements, "dict"):
                    r_dict = requirements.dict(by_alias=True)
                else:
                    r_dict = requirements

                # Construct request body for Pincer /verify endpoint
                verification_request = {
                    "paymentPayload": p_dict,
                    "paymentRequirements": r_dict,
                    # We don't have session_id here, Pincer will extract it from payload/requirements or generate new one
                    # But if Pincer returns it, we are good.
                    "session_id": None 
                }
                
                # Use the SDK's authenticated HTTP client
                response = await self.client._http.post("/verify", json=verification_request)
                response.raise_for_status()
                data = response.json()
                
                from .types import SponsoredOffer
                
                sponsors = []
                if "sponsors" in data:
                    sponsors = [SponsoredOffer(**s) for s in data["sponsors"]]

                result = PincerVerificationResponse(
                    is_valid=data.get("isValid"),
                    invalid_reason=data.get("invalidReason"),
                    payer=data.get("payer"),
                    sponsors=sponsors
                )
                
                # Store result in ContextVar for access in route handlers
                verification_var.set(result)
                return result

            async def settle(self, payload, requirements):
                """Settle payment via Pincer."""
                from x402.schemas import SettleResponse
                
                # Serialize payload and requirements
                # IMPORTANT: Use by_alias=True to preserve camelCase field names
                p_dict = payload.model_dump(by_alias=True, mode='json') if hasattr(payload, "model_dump") else (payload.dict(by_alias=True) if hasattr(payload, "dict") else payload)
                r_dict = requirements.model_dump(by_alias=True, mode='json') if hasattr(requirements, "model_dump") else (requirements.dict(by_alias=True) if hasattr(requirements, "dict") else requirements)

                request_body = {
                    "paymentPayload": p_dict,
                    "paymentRequirements": r_dict
                }
                
                # Use the SDK's authenticated HTTP client
                response = await self.client._http.post("/settle", json=request_body)
                response.raise_for_status()
                data = response.json()
                
                return SettleResponse(**data)
            
            def get_supported(self):
                """Get supported payment kinds/schemes."""
                import httpx
                from x402.schemas import SupportedResponse
                
                # Use a sync client for initialization as this method is called synchronously
                # by x402 server initialization
                base_url = str(self.client.base_url)
                with httpx.Client(base_url=base_url) as client:
                    response = client.get("/supported")
                    response.raise_for_status()
                    return SupportedResponse(**response.json())

        facilitator = PincerFacilitatorClient(self.client)
        return x402ResourceServer(facilitator)
