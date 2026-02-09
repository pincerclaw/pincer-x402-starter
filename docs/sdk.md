# SDK Reference

## `PincerPaymentMiddleware`

The recommended way to protect your API. It handles the x402 challenge-response loop and automatically injects Pincer-specific data (like `sponsors`).

### Usage (FastAPI)

```python
from src.pincer_sdk.middleware import PincerPaymentMiddleware
from x402.server import x402ResourceServer

# ... initialize client and facilitator
server = x402ResourceServer(facilitator)

# Add middleware to your app
app.add_middleware(PincerPaymentMiddleware, routes=routes, server=server)
```

## `PincerFacilitatorClient`

A specialized `FacilitatorClient` that preserves Pincer-specific data (like `sponsors`) during the verification process.

### Usage

```python
# Standard way to get the facilitator from the client
facilitator = client.facilitator()
```

### Accessing Sponsors

After verification, you can access sponsors in your route handlers:

```python
@app.get("/premium-data")
async def get_data(request: Request):
    # Populated by PincerPaymentMiddleware
    payment = getattr(request.state, "payment", None)
    sponsors = getattr(payment, "sponsors", []) if payment else []

    return {"sponsors": sponsors, ...}
```
