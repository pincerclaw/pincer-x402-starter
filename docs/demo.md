# Running the Demo

See the Pincer protocol in action with a complete end-to-end simulation.

## Overview

The demo simulates a complete interaction cycle:

1.  **Buyer** requests a resource.
2.  **Seller** challenges with a 402 Payment Required.
3.  **Buyer** pays via Solana (Devnet).
4.  **Seller** verifies and returns content.
5.  **Sponsor** (Shake Shack) rebates the fee.

## Prerequisite

Clone the starter repository:

```bash
git clone https://github.com/pincerclaw/pincer-x402-starter
cd pincer-x402-starter
pip install .
```

## Run the Demo

Execute the agent simulation:

```bash
uv run src/agent/demo.py
```

### What you'll see

```text
🚀 Pincer x402 Demo
...
Step 1: Request paywalled content (no payment)
HTTP 402 Payment Required
...
Step 3: Request with payment proof
HTTP 200 OK
...
🎁 Sponsor Offers:
   💰 Shake Shack: Get x402 fee rebate on your first order
```
