# Buyer Guide

**Role**: You are a Buyer (Agent/Client). You want to access high-value APIs gated by Pincer.

## How it Works

Pincer APIs use the standard `x402` protocol. You don't need a proprietary client, but using `pincer-sdk` or `x402` client libraries makes it automatic.

## Making a Request

```python
from x402.client import x402Client

# 1. Initialize Client with a Wallet
client = x402Client(wallet=my_solana_wallet)

# 2. Making a Request
# The client automatically handles the 402 challenge/response loop
response = await client.get("https://pincer.zeabur.app/resource/premium-data")

print(response.json())
```

### What happens under the hood?

1.  **Initial Request**: You send a normal GET request.
2.  **Challenge**: Server replies `402 Payment Required` with a header `WWW-Authenticate: x402 ...`.
3.  **Sign**: Your client looks at the cost, signs a transaction (or uses a payment channel).
4.  **Retry**: Your client allows the payment proof in the `Authorization` or `X-Payment` header and retries.
5.  **Success**: Server returns `200 OK`.
