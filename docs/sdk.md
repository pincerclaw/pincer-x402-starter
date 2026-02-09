# SDK Reference

## `MerchantClient`

The main interface for integrating Pincer payment protection into your API. Accessed via `client.merchant`.

## `PincerFacilitatorClient`

A specialized `FacilitatorClient` that preserves Pincer-specific data (like `sponsors`) during the verification process.

### Usage

```python
from pincer_sdk.facilitator import PincerFacilitatorClient
from x402.server import x402ResourceServer

# Standard Composition Pattern
facilitator = PincerFacilitatorClient(client)
server = x402ResourceServer(facilitator)
```

### `verify`

Standard `x402` verify method, but captures the `sponsors` list into a `ContextVar`.

```python
async def verify(self, payload, requirements) -> PincerVerificationResponse
```

### `get_active_sponsors`

Access the sponsors captured during the verification of the current request.

```python
# Helper on the main client
sponsors = client.merchant.get_active_sponsors()
```
