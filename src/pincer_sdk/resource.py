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

        # Subclass x402ResourceServer to attach sponsors to the result
        # Subclass x402ResourceServer to attach sponsors to the result
        class PincerResourceServer(x402ResourceServer):
            def __init__(self, facilitator):
                super().__init__(facilitator)
                self._http_helper = None

            async def handle_request(self, request, requirements):
                """Handle manual request verification.
                
                Args:
                    request: FastAPI Request object
                    requirements: RouteConfig or list of PaymentOptions
                
                Returns:
                    Union[Response, PincerVerificationResponse]
                """
                from fastapi.responses import JSONResponse, Response, HTMLResponse
                from x402.http import x402HTTPResourceServer, HTTPRequestContext
                import inspect
                # Try to import FastAPI adapter, fallback if internal
                try:
                    from x402.http.middleware.fastapi import FastAPIAdapter
                except ImportError:
                     # Simple adapter fallback if import fails
                     from x402.http.types import HTTPAdapter
                     class FastAPIAdapter(HTTPAdapter):
                         def __init__(self, request): self._r = request
                         def get_header(self, n): return self._r.headers.get(n)
                         def get_method(self): return self._r.method
                         def get_path(self): return self._r.url.path
                         def get_url(self): return str(self._r.url)
                         def get_accept_header(self): return self._r.headers.get("accept", "")
                         def get_user_agent(self): return self._r.headers.get("user-agent", "")
                         def get_query_params(self): return dict(self._r.query_params)
                         def get_query_param(self, n): return self._r.query_params.get(n)
                         def get_body(self): return None

                
                # Create context
                adapter = FastAPIAdapter(request)
                context = HTTPRequestContext(
                    adapter=adapter,
                    path=request.url.path,
                    method=request.method,
                    payment_header=(
                        request.headers.get("payment-signature") or 
                        request.headers.get("x-payment") or
                        request.headers.get("authorization")
                    ),
                )

                # Strategy: Create a fresh helper for each request with a wildcard route matching the requirements.
                # This ensures x402HTTPResourceServer logic finds the route config and enforces payment.
                # We do this because x402HTTPResourceServer ignores the paywall_config arg for payment requirement checks.

                # Normalize requirements to RouteConfig
                from x402.http.types import RouteConfig
                final_config = requirements
                
                if isinstance(requirements, list):
                    # List of PaymentOptions
                    final_config = RouteConfig(accepts=requirements)
                elif isinstance(requirements, dict) and "accepts" not in requirements:
                     # Assume it's a dict based config intended for RouteConfig
                     # But if it lacks accepts, x402 might fail. Best effort.
                     pass

                # Create helper with wildcard route to match ANY path
                routes = {"*": final_config}
                http_helper = x402HTTPResourceServer(self, routes)
                
                # Initialize (uses cached capabilities from self, so it's efficient)
                if hasattr(http_helper, "initialize"):
                     if inspect.iscoroutinefunction(http_helper.initialize):
                         await http_helper.initialize()
                     else:
                         http_helper.initialize()

                result = await http_helper.process_http_request(context)

                if result.type == "payment-verified":
                    # Return the success object from ContextVar (populated by PincerFacilitatorClient.verify)
                    return verification_var.get()
                    
                elif result.type == "payment-error":
                    # Return 402/Error Response
                    resp = result.response
                    if not resp:
                        return JSONResponse({"error": "Payment required"}, status_code=402)
                    
                    # resp.body is likely bytes/str, usage of JSONResponse would double-serialize or fail
                    # Use generic Response
                    return Response(
                        content=resp.body or b"", 
                        status_code=resp.status, 
                        headers=resp.headers,
                        media_type=resp.headers.get("content-type", "application/json")
                    )
                
                # Should not happen if requirements provided
                return JSONResponse({"error": f"Payment verification failed: unknown result type {result.type}"}, status_code=500)

        facilitator = PincerFacilitatorClient(self.client)
        return PincerResourceServer(facilitator)
