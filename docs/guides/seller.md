# Seller Integration

**Role**: You are a Seller (API Provider). You want to monetize your data/services and accept crypto micro-payments from Buyers (Agents).

## Prerequisite

Install the Pincer SDK:

```bash
pip install pincer-sdk
```

## Step 1: Initialize Server

The `x402_server` handles the complex negotiation, payment headers, and validation for you.

```python
from pincer_sdk.client import PincerClient
from pincer_sdk.facilitator import PincerFacilitatorClient
from x402.server import x402ResourceServer

# 1. Initialize Pincer Client
# Uses PINCER_URL from env (e.g. https://pincer.zeabur.app)
client = PincerClient(api_key="...")

# 2. Create Server (Composition Pattern)
# Use Pincer's client to handle extra data (like sponsors)
facilitator = PincerFacilitatorClient(client)

# Create standard x402 server
server = x402ResourceServer(facilitator)

# Register schemes (e.g. EVM, Solana) - see x402 docs for details
# server.register(...)
```

## Step 2: Protect your Route (Middleware)

The simplest way to protect your API is using the **Pincer SDK Middleware**.

```python
from pincer_sdk.middleware import PincerPaymentMiddleware

# 1. Define Routes & Costs
routes = {
    "/premium-data": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to="0x...",
                price="$0.01",
                network="solana:mainnet"
            )
        ]
    )
}

# 2. Add Middleware
app.add_middleware(PincerPaymentMiddleware, routes=routes, server=server)

# 3. Handle Request (Payment Verified)
@app.get("/premium-data")
async def get_premium_data(request: Request):
    # If we reach here, payment is already verified!

    # 4. Access Active Sponsors (Rebates)
    # The Pincer middleware automatically populates sponsors
    payment = getattr(request.state, "payment", None)
    sponsors = getattr(payment, "sponsors", []) if payment else []

    return {
        "status": "paid",
        "data": "Secret Intelligence",
        "sponsors": sponsors
    }
```
