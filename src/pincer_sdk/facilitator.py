"""Facilitator client for Pincer protocol."""

import logging
from contextvars import ContextVar
from typing import Optional, List, Any, TYPE_CHECKING
from pydantic import BaseModel

from .types import SponsoredOffer

if TYPE_CHECKING:
    from .client import PincerClient

logger = logging.getLogger(__name__)

# Context variable to store verification result for the current request
# Exposed here so users/merchant client can access it
verification_var: ContextVar[Optional[Any]] = ContextVar("verification_result", default=None)


class PincerVerificationResponse(BaseModel):
    """Extended verification response with Pincer-specific fields."""
    is_valid: bool
    invalid_reason: Optional[str] = None
    payer: Optional[str] = None
    sponsors: List[SponsoredOffer] = []
    
    model_config = {"extra": "allow"}


class PincerFacilitatorClient:
    """Client for communicating with Pincer Facilitator.
    
    Compatible with x402 FacilitatorClient interface but preserves Pincer-specific data.
    """

    def __init__(self, client: "PincerClient"):
        self.client = client

    async def verify(self, payload, requirements):
        """Verify payment and capture Pincer-specific data (sponsors)."""
        # Serialize payload and requirements for Pincer API
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
        }
        
        try:
            response = await self.client._http.post("/verify", json=verification_request)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Pincer verification failed: {e}")
            raise

        sponsors = []
        if "sponsors" in data:
            sponsors = [SponsoredOffer(**s) for s in data["sponsors"]]

        # Create extended response object
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
