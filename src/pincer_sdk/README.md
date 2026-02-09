# Pincer SDK for Python

**Simple, machine-native payments for the AI economy.**

The Pincer SDK is a lightweight wrapper for the **x402 protocol**, specifically designed to handle **Post-Pay Rebates** and sponsored access. It enables API providers (Sellers) to monetize their services while allowing sponsors (Merchants) to subsidize the cost for high-intent agents.

---

## 🚀 Quick Start

### Installation

```bash
pip install pincer-sdk
```

### 1. For Sellers: Protect your API

Sellers use Pincer to verify x402 payments and identify active sponsors using the built-in middleware.

```python
from src.pincer_sdk import PincerClient
from src.pincer_sdk.middleware import PincerPaymentMiddleware
from x402.server import x402ResourceServer

client = PincerClient(
    base_url="https://your-pincer-url.com",
    api_key="your_api_key"
)

# Initialize standard x402 server with Pincer facilitator
server = x402ResourceServer(client.facilitator())

# Add Pincer middleware to your FastAPI app
app.add_middleware(PincerPaymentMiddleware, routes=routes, server=server)

# Your FastAPI route
@app.get("/premium-data")
async def get_data(request: Request):
    # Payment is already verified here!
    # Sponsors are automatically injected into the request state
    payment = getattr(request.state, "payment", None)
    sponsors = getattr(payment, "sponsors", []) if payment else []

    return {
        "data": "Premium content",
        "applied_sponsors": sponsors
    }
```

### 2. For Merchants: Report Conversions

Merchants notify Pincer when a transaction occurs to trigger user rebates.

```python
from pincer_sdk import PincerClient

async with PincerClient(
    base_url="https://pincer.zeabur.app",  # URL is now required
    webhook_secret="your_secret"
) as pincer:
    await pincer.report_conversion(
        session_id="sess-123",
        user_address="0x...",
        purchase_amount=25.0,
        merchant_id="my-store"
    )
```

## 🏗 Why Pincer SDK?

The Pincer SDK enhances the base `x402` experience by:

- **Injecting Sponsorship Data**: Automatically capturing sponsor offers during the verification phase.
- **Simplifying Webhooks**: Providing signed conversion reporting for merchants out of the box.
- **Managing Identity**: Properly handling session IDs across the payment lifecycle.

## 📄 License

MIT
