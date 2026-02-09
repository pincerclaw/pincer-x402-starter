"""Middleware for Pincer SDK.

This module provides a drop-in replacement for x402 middleware that correctly
handles Pincer-specific data fields (like sponsors) which are otherwise
dropped by the strict x402 SDK validation.
"""

import asyncio
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from starlette.types import ASGIApp

from x402.http.middleware.fastapi import FastAPIAdapter
from x402.http.types import HTTPRequestContext, HTTPProcessResult, RouteConfig
from x402.http.x402_http_server import x402HTTPResourceServer
from x402.schemas.responses import VerifyResponse
from x402.server import x402ResourceServer

from .client import PincerClient
from .facilitator import PincerFacilitatorClient

# ------------------------------------------------------------------------------
# Monkey-patch: Enable Extra Fields
# ------------------------------------------------------------------------------
# We must allow extra fields on VerifyResponse to prevent Pydantic from
# stripping out the 'sponsors' list returned by the Pincer Facilitator.
VerifyResponse.model_config['extra'] = 'allow'


class PincerHTTPResourceServer(x402HTTPResourceServer):
    """Custom HTTP Resource Server that captures extra fields (sponsors).
    
    This server extends the standard x402HTTPResourceServer to ensure that
    extra data returned by the facilitator (like 'sponsors') is preserved
    and accessible in the result, rather than being discarded.
    """
    
    async def process_http_request(
        self, 
        context: HTTPRequestContext, 
        paywall_config: Any = None
    ) -> HTTPProcessResult:
        """Process HTTP request and capture sponsor data."""
        # We need to copy the logic because strict extraction in base class drops extras
        # But for maintenance, we rely on _process_request_core being available.
        gen = self._process_request_core(context, paywall_config)
        result = None
        exception = None
        captured_sponsors = []
        
        try:
            while True:
                if exception is not None:
                    phase, target, ctx = gen.throw(exception)
                    exception = None
                else:
                    phase, target, ctx = gen.send(result)

                if phase == "resolve_options":
                    route_config = target
                    timeout = route_config.hook_timeout_seconds
                    try:
                        result = await self._build_payment_requirements_from_options(
                            route_config.accepts, ctx, timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        exception = TimeoutError("Hook execution timed out")
                        result = None
                    except Exception as e:
                        exception = e
                        result = None
                elif phase == "verify_payment":
                    payload, reqs = target
                    # This returns VerifyResponse (now with sponsors in __dict__ due to monkey-patch)
                    result = await self._server.verify_payment(payload, reqs)
                    
                    # Capture sponsors
                    if hasattr(result, "sponsors"):
                        captured_sponsors = getattr(result, "sponsors")
                    elif hasattr(result, "__dict__") and "sponsors" in result.__dict__:
                        captured_sponsors = result.__dict__["sponsors"]
                        
                else:
                    result = None
        except StopIteration as e:
            http_result = e.value
            # Attach captured sponsors to the result object dynamically
            if http_result.type == "payment-verified":
                setattr(http_result, "sponsors", captured_sponsors)
            return http_result


class PincerPaymentMiddleware(BaseHTTPMiddleware):
    """Payment middleware for Pincer x402 integration.
    
    This middleware automatically handles:
    1. Setting up the Pincer Client and Facilitator
    2. Configuring the Resource Server
    3. Processing payments and verification
    4. Injecting 'sponsors' into request.state.payment
    """

    def __init__(
        self, 
        app: ASGIApp, 
        routes: dict[str, RouteConfig], 
        server: x402ResourceServer
    ):
        """Initialize the middleware.
        
        Args:
            app: The ASGI application.
            routes: The route configuration.
            server: The initialized x402ResourceServer (must use PincerFacilitatorClient).
        """
        super().__init__(app)
        # Initialize our Custom HTTP Server
        self.http_server = PincerHTTPResourceServer(server, routes)
        self.http_server.initialize()

    async def dispatch(self, request: Request, call_next):
        # Create adapter and context
        adapter = FastAPIAdapter(request)
        context = HTTPRequestContext(
            adapter=adapter,
            path=request.url.path,
            method=request.method,
            payment_header=(
                adapter.get_header("payment-signature") or adapter.get_header("x-payment")
            ),
        )

        # Check if route requires payment (before initialization)
        if not self.http_server.requires_payment(context):
            return await call_next(request)

        # Process payment request
        result = await self.http_server.process_http_request(context)

        if result.type == "no-payment-required":
            return await call_next(request)

        if result.type == "payment-error":
            # Simplified error response
            if result.response:
                if result.response.is_html:
                    return HTMLResponse(
                        content=result.response.body,
                        status_code=result.response.status,
                        headers=result.response.headers,
                    )
                else:
                    return JSONResponse(
                        content=result.response.body or {},
                        status_code=result.response.status,
                        headers=result.response.headers,
                    )
            return JSONResponse(
                 content={"error": "Payment required"},
                 status_code=402,
            )

        if result.type == "payment-verified":
            # Store payment info in request state
            request.state.payment_payload = result.payment_payload
            request.state.payment_requirements = result.payment_requirements
            
            # INJECT SPONSORS
            sponsors = getattr(result, "sponsors", [])
            
            # Create a simple object to hold payment state including sponsors
            class PaymentContext:
                pass
            ctx = PaymentContext()
            ctx.sponsors = sponsors
            request.state.payment = ctx

            # Call protected route
            response = await call_next(request)

            # Don't settle on error responses
            if response.status_code >= 400:
                return response

            # Just call settle
            try:
                settle_result = await self.http_server.process_settlement(
                    result.payment_payload,
                    result.payment_requirements,
                )
                
                # Add settlement headers
                if settle_result.success:
                     for k, v in settle_result.headers.items():
                         response.headers[k] = v
                         
            except Exception as e:
                # Log usage but don't fail request
                print(f"Settlement error: {e}")

            return response

        # Fallthrough
        return await call_next(request)
