---
name: Pincer x402 Integration
description: Learn how to integrate with the Pincer x402 Payment Protocol using the Python SDK. This skill covers how Agents can Act as Sellers (Monetize Data), Buyers (Pay for Resources), or Sponsors (Advertise).
version: 0.1.0
---

# Pincer x402 Integration

Pincer is a facilitator for the **x402 Payment Protocol**, enabling crypto micro-payments and sponsored access for API resources.

Agents typically interact with Pincer in three ways:

1.  **As a Seller**: You have valuable data/tool and want to charge for it (or allow sponsored access).
2.  **As a Buyer**: You need to access a protected resource and must pay for it (or use a sponsor).
3.  **As a Sponsor**: You want to pay for other people's access in exchange for their attention (ads).

## Role 1: Monetize Your Agent (Seller)

If you are an Agent offering a service (e.g., "Premium Search", "Data Analysis"), use the `pincer-sdk` to protect your endpoints.

### Prerequisites

- Install SDK: `uv add pincer-sdk`
- Env Vars: `PINCER_URL=https://pincer.zeabur.app`

### Implementation

Use the `PincerPaymentMiddleware` to automatically handle payment verification.

```python
from fastapi import FastAPI, Request
from pincer_sdk.client import PincerClient
from pincer_sdk.facilitator import PincerFacilitatorClient
from pincer_sdk.middleware import PincerPaymentMiddleware
from x402.server import x402ResourceServer
from x402.http.types import RouteConfig, PaymentOption

app = FastAPI()

# 1. Setup Pincer Facilitator
client = PincerClient(base_url="https://pincer.zeabur.app")
facilitator = PincerFacilitatorClient(client)
server = x402ResourceServer(facilitator)

# 2. Define Payment Rules
routes = {
    "/premium-tool": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to="<YOUR_WALLET_ADDRESS>",
                price="$0.01",  # Price in USD
                network="solana:mainnet" # or base:sepolia
            )
        ]
    )
}

# 3. Protect App
app.add_middleware(PincerPaymentMiddleware, routes=routes, server=server)

@app.get("/premium-tool")
async def premium_tool(request: Request):
    # Payment is already verified!
    # Check for sponsors (rebates)
    payment = getattr(request.state, "payment", None)
    sponsors = getattr(payment, "sponsors", [])

    return {"data": "Expensive result", "sponsors": sponsors}
```

## Role 2: Access Paid Resources (Buyer)

If you are an Agent trying to access a protected tool, you will receive a `402 Payment Required` error. You must sign a payment to proceed.

### Prerequisites

- Wallet Private Key (Solana or EVM)

### Implementation

Use the `x402` client to automatically handle the 402 challenge-response loop.

```python
from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client

# 1. Initialize Client with Wallet
client = x402Client()
signer = KeypairSigner.from_base58("<YOUR_PRIVATE_KEY>")
register_exact_svm_client(client, signer)

# 2. Access Protected Resource
async with x402HttpxClient(client) as http:
    response = await http.get("https://premium-agent-service.com/tool")

    if response.status_code == 200:
        print("Success!", response.json())

        # Check for Sponsors/Rebates in response
        # (Pincer services often return 'sponsors' list)
```

## Role 3: Run Ad Campaigns (Sponsor)

If you want to sponsor user transactions (pay their fees in exchange for them viewing your ad), you can create a Campaign.

### Implementation

Currently, Campaigns are loaded from a JSON configuration file.
Modify `src/data/campaigns.json` in the Pincer deployment.

### Campaign Schema

```json
[
  {
    "id": "my-promo-campaign",
    "merchant_name": "My Brand",
    "offer_text": "Get x402 fee rebate on your first order",

    "rebate": {
      "amount": 0.1, // Amount to pay back to user (Rebate)
      "asset": "USDC", // Currency (USDC)
      "network": "solana:devnet" // Network to pay on
    },

    "budget": {
      "total": 100.0, // Total budget for this campaign
      "remaining": 100.0, // Remaining budget
      "asset": "USDC"
    },

    "coupons": [
      {
        "code": "WELCOME20",
        "description": "20% off your purchase",
        "discount_type": "percentage",
        "discount_value": 20.0
      }
    ]
  }
]
```
