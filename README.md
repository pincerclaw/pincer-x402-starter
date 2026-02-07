# Pincer x402 Reference Implementation

A production-quality reference implementation of Pincer's x402-sponsored access flow, demonstrating post-pay rebates for paywalled content.

## Overview

This demo implements an end-to-end flow where:

1. **Users pay for premium content** via x402 protocol (TopEats restaurant recommendations)
2. **Receive sponsored offers** after payment verification (Shake Shack cashback offer)
3. **Purchase from sponsored merchant** and trigger conversion tracking
4. **Get rebates** automatically settled from Pincer treasury

**Payment Model**: POST-PAY + REBATE (user pays first, receives rebatefrom sponsor after purchase)

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│   Agent     │         │   TopEats    │         │    Pincer    │
│   Client    │◄───402──┤  (Paywall)   │◄────────┤ (Facilitator)│
│             │         │              │  verify │              │
│             │─payment─►              │────────►│              │
│             │◄──200+──┤              │◄offers──┤              │
│             │  offers │              │         │              │
└──────┬──────┘         └──────────────┘         └──────┬───────┘
       │                                                 │
       │ checkout                                        │ rebate
       │                                                 │
       ▼                                                 ▼
┌─────────────┐                                  ┌──────────────┐
│ Shake Shack │                                  │   Treasury   │
│  (Merchant) │──────────webhook────────────────►│    Wallet    │
└─────────────┘                                  └──────────────┘
```

### Components

1. **TopEats** (`src/topeats/server.py`) - Paywalled content server
   - Protects restaurant recommendations behind x402
   - Returns 402 for unpaid requests
   - Fetches sponsored offers from Pincer after payment verification
   - Returns 200 with content + offers

2. **Pincer** (`src/pincer/`) - Facilitator + Sponsorship Service
   - `verification.py` - x402 payment verification (neutral to sponsorship)
   - `offers.py` - Sponsor offer generation with budget checking
   - `webhooks.py` - Conversion webhook handling (idempotency + anti-replay)
   - `payout.py` - Rebate settlement from treasury
   - `server.py` - Main FastAPI application

3. **Shake Shack** (`src/merchant/server.py`) - Demo Merchant
   - Simulates checkout flow
   - Sends HMAC-signed webhooks to Pincer

4. **Agent** (`src/agent/demo.py`) - Demo Client Script
   - Simulates end-to-end user journey
   - Based on Coinbase x402 httpx client

### Shared Infrastructure

- `src/config.py` - Centralized configuration via environment variables
- `src/models.py` - Pydantic data models for type safety
- `src/database.py` - SQLite ledger with async operations
- `src/logging_utils.py` - Correlation ID-based structured logging

## Setup

### Prerequisites

- Python 3.10+
- pip or uv (recommended)

### Installation

1. **Clone/navigate to the repository:**

   ```bash
   cd pincer-x402-starter
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   Or with uv (faster):

   ```bash
   uv pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env with your keys
   ```

   **Required variables:**
   - `EVM_PRIVATE_KEY` or `SVM_PRIVATE_KEY` - Your wallet for paying content fees
   - `TREASURY_EVM_PRIVATE_KEY` or `TREASURY_SVM_PRIVATE_KEY` - Treasury wallet for rebates

   **Note**: For MVP demo, the payout engine runs in simulation mode if treasury keys aren't configured. Real on-chain transfers require funded wallets on Base Sepolia (EVM) or Solana Devnet (SVM).

4. **Initialize database:**

   ```bash
   python scripts/init_ledger.py
   ```

   This creates `pincer.db` with schema and default Shake Shack campaign ($100 budget, $5 rebates).

## Running the Demo

### Option 1: Manual (Recommended for first run)

Open four terminal windows:

**Terminal 1 - TopEats:**

```bash
python src/topeats/server.py
# Runs on http://localhost:4021
```

**Terminal 2 - Pincer:**

```bash
python src/pincer/server.py
# Runs on http://localhost:4022
```

**Terminal 3 - Merchant:**

```bash
python src/merchant/server.py
# Runs on http://localhost:4023
```

**Terminal 4 - Agent Demo:**

```bash
python src/agent/demo.py
```

### Option 2: Using tmux/screen (Advanced)

```bash
# Start all services in background
tmux new-session -d -s topeats 'python src/topeats/server.py'
tmux new-session -d -s pincer 'python src/pincer/server.py'
tmux new-session -d -s merchant 'python src/merchant/server.py'

# Run demo
python src/agent/demo.py

# View logs
tmux attach -t topeats  # Ctrl+B, D to detach
tmux attach -t pincer
tmux attach -t merchant
```

## Expected Output

### Phase A: Paywalled Content Access

```
====================================================================
  Phase A: Requesting Premium Content from TopEats
====================================================================

📍 Step 1: Initial request to /recommendations (no payment)

✅ Received HTTP 402 Payment Required
   Payment header: eyJ...

📍 Step 2: User approves payment

   💰 Amount: $0.1
   🔗 Networks: eip155:84532 or solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1
   ✅ Payment approved by user

📍 Step 3: Retry request with payment proof

   💼 Using EVM account: 0x...

✅ Payment verified! Received HTTP 200

📋 Received 5 restaurant recommendations
   1. Eleven Madison Park - Contemporary American ($$$$)
   2. Peter Luger Steak House - Steakhouse ($$$$)
   3. Shake Shack - Burgers ($$)
```

### Phase B: Sponsored Offers

```
====================================================================
  Phase B: Sponsored Offers Received
====================================================================

🎁 Received 1 sponsored offer(s):

   Offer 1:
      Merchant: Shake Shack
      Offer: Get $5.00 cashback on your first order
      Rebate: $5.00
      Session ID: sess-abc123

📍 User selects offer: Shake Shack
```

### Phase C: Rebate Settlement

```
====================================================================
  Phase C: Merchant Purchase and Rebate Settlement
====================================================================

📍 Step 1: User proceeds to merchant checkout

   🍔 Merchant: Shake Shack
   💰 Order amount: $25.00
   🎟️  Session ID: sess-abc123

✅ Checkout completed!
   Order ID: order-def456
   Webhook sent: True
   Webhook ID: wh-ghi789

📍 Step 2: Waiting for rebate settlement...

   ⏳ Pincer is processing the conversion webhook...
   🔒 Verifying: idempotency, anti-replay, budget
   💸 Initiating rebate transfer

✅ Rebate should be settled!
   💵 Amount: $5.00
   👛 To: 0x...
   🔗 Network: eip155:84532

   Note: Check Pincer service logs for transaction hash
```

## Verification

### 1. Check Correlation ID Across Logs

All services log with the same correlation ID for a single user journey:

```bash
# In TopEats logs
{"correlation_id": "corr-a1b2c3d4e5f6", "message": "Payment verified..."}

# In Pincer logs
{"correlation_id": "corr-a1b2c3d4e5f6", "message": "Generated 1 offers..."}

# In Merchant logs
{"correlation_id": "corr-a1b2c3d4e5f6", "message": "Sending conversion webhook..."}
```

### 2. Query Database

```bash
# View all settlements
sqlite3 pincer.db "SELECT * FROM settlements;"

# View settlement for specific session
sqlite3 pincer.db "SELECT * FROM settlements WHERE session_id='sess-abc123';"

# Check campaign budget
sqlite3 pincer.db "SELECT remaining_budget_usd FROM campaigns WHERE campaign_id='shake-shack-promo';"

# Verify idempotency (should show 1 webhook per session)
sqlite3 pincer.db "SELECT COUNT(*) FROM webhooks WHERE session_id='sess-abc123';"
```

### 3. Test Reliability Features

**Idempotency (webhook deduplication):**

```bash
# Send same webhook twice
curl -X POST http://localhost:4022/webhooks/conversion \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: <signature>" \
  -d '{"webhook_id":"wh-same","session_id":"sess-test",...}'

# Second request should return same result without double-processing
```

**Anti-replay (session reuse prevention):**

```bash
# Try to use same session_id in two different webhooks
# Second webhook should fail with "Rebate already settled" error
```

## Reset Demo State

To run the demo again from a clean state:

```bash
./scripts/reset_demo.sh
```

This deletes `pincer.db` and reinitializes with fresh sponsor budget.

## Running Tests

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test
pytest tests/unit/test_idempotency.py -v
pytest tests/unit/test_anti_replay.py -v
pytest tests/unit/test_budget_management.py -v
pytest tests/unit/test_signature_verification.py -v
```

### Integration Tests

```bash
# Run integration tests (requires services running)
pytest tests/integration/ -v
```

### With Coverage

```bash
pytest --cov=src --cov-report=html tests/
open htmlcov/index.html
```

## Configuration Reference

All configuration via `.env` file:

| Variable                    | Description                             | Default                      |
| --------------------------- | --------------------------------------- | ---------------------------- |
| `EVM_PRIVATE_KEY`           | Your EVM wallet private key             | -                            |
| `SVM_PRIVATE_KEY`           | Your Solana wallet private key          | -                            |
| `TREASURY_EVM_PRIVATE_KEY`  | Treasury EVM private key for rebates    | -                            |
| `TREASURY_SVM_PRIVATE_KEY`  | Treasury Solana private key for rebates | -                            |
| `TOPEATS_PORT`              | TopEats server port                     | 4021                         |
| `PINCER_PORT`               | Pincer server port                      | 4022                         |
| `MERCHANT_PORT`             | Merchant server port                    | 4023                         |
| `FACILITATOR_URL`           | x402 facilitator URL                    | https://x402.org/facilitator |
| `WEBHOOK_SECRET`            | Shared secret for webhook HMAC          | change_me_in_production      |
| `CONTENT_PRICE_USD`         | Price for TopEats content               | 0.10                         |
| `SPONSOR_REBATE_AMOUNT_USD` | Rebate amount                           | 5.00                         |
| `SPONSOR_TOTAL_BUDGET_USD`  | Campaign budget                         | 100.00                       |
| `LOG_LEVEL`                 | Logging level                           | INFO                         |
| `LOG_FORMAT`                | Log format (json/text)                  | json                         |

## Project Structure

```
pincer-x402-starter/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
├── .env                         # Your config (gitignored)
├── pytest.ini                   # Pytest configuration
├── pincer.db                    # SQLite database (gitignored)
├── scripts/
│   ├── init_ledger.py           # Database initialization
│   └── reset_demo.sh            # Reset demo state
├── src/
│   ├── config.py                # Configuration management
│   ├── models.py                # Data models
│   ├── database.py              # SQLite interface
│   ├── logging_utils.py         # Correlation ID logging
│   ├── topeats/
│   │   └── server.py            # Paywalled content server
│   ├── pincer/
│   │   ├── server.py            # Main FastAPI app
│   │   ├── verification.py      # x402 verification
│   │   ├── offers.py            # Offer generation
│   │   ├── webhooks.py          # Webhook handling
│   │   └── payout.py            # Rebate settlement
│   ├── merchant/
│   │   └── server.py            # Demo merchant
│   └── agent/
│       └── demo.py              # Demo client script
└── tests/
    ├── unit/
    │   ├── test_idempotency.py
    │   ├── test_anti_replay.py
    │   ├── test_budget_management.py
    │   └── test_signature_verification.py
    └── integration/
        └── (integration tests TBD)
```

## Implementation Notes

### Based on Coinbase x402 Examples

This implementation is adapted from:

- [x402 Python FastAPI server example](https://github.com/coinbase/x402/tree/main/examples/python/servers/fastapi)
- [x402 Python httpx client example](https://github.com/coinbase/x402/tree/main/examples/python/clients/httpx)

Key adaptations:

- Added Pincer offer injection after payment verification
- Integrated webhook-based rebate settlement
- Implemented idempotency and anti-replay protection
- Added centralized budget management ledger

### Reliability Guarantees

#### Idempotency

- Webhook `webhook_id` is unique and tracked in database
- Duplicate webhooks return previous result without reprocessing
- Prevents double rebates from merchant webhook retries

#### Anti-Replay

- Payment `session_id` is tracked with `rebate_settled` flag
- Once settled, session cannot be reused for another rebate
- Prevents malicious replay of payment proofs

#### Atomicity

- Budget reservation is atomic (database lock)
- Webhook processing uses database transactions
- Settlement records created before payout attempt

#### Observability

- Correlation IDs trace requests across all services
- Structured JSON logging for production monitoring
- All state changes recorded in database

### Limitations (MVP)

- **No on-chain escrow**: Budgets managed centrally (trust Pincer)
- **Simulated payouts**: Treasury transfers use simulation mode by default
- **Single sponsor**: Hardcoded to one campaign (Shake Shack)
- **No offer selection logic**: Always returns single offer if budget available
- **Simplified verification**: x402 verification uses placeholder (full SDK integration needed)

### Production TODOs

- [ ] Complete x402 verification integration (currently placeholder)
- [ ] Implement real EVM/SVM payout transfers
- [ ] Add price oracle for USD → SOL conversion
- [ ] Support multiple sponsor campaigns
- [ ] Add campaign scheduling and activation logic
- [ ] Implement offer ranking/selection algorithms
- [ ] Add offer click/conversion analytics
- [ ] Deploy on-chain escrow for trustless budgets
- [ ] Add webhook retry mechanism
- [ ] Implement rate limiting
- [ ] Add administrative API for campaign management
- [ ] Set up production monitoring and alerting

## Troubleshooting

### "Missing required environment variables"

**Solution**: Copy `.env.example` to `.env` and fill in at least one payment method (EVM or SVM keys).

### "402 Payment Required" but payment fails

**Check**: Ensure your wallet has sufficient funds on Base Sepolia or Solana Devnet.  
**Testnet faucets**:

- Base Sepolia: https://www.coinbase.com/faucets/base-sepolia-faucet
- Solana Devnet: https://faucet.solana.com

### "Campaign not found" during offer generation

**Solution**: Run `python scripts/init_ledger.py` to initialize the database.

### "No sponsored offers received"

**Check**: Campaign budget may be exhausted. Reset with `./scripts/reset_demo.sh`.

### Webhook signature verification fails

**Check**: Ensure `WEBHOOK_SECRET` matches in both merchant and Pincer `.env` files.

## License

This reference implementation is provided as-is for demonstration purposes.

## Contributing

This codebase is designed to be clean, modular, and extensible. Key extension points:

- Add new payment schemes in `pincer/verification.py`
- Add new sponsor campaigns in database
- Customize offer generation logic in `pincer/offers.py`
- Add offer selection algorithms
- Extend payout methods in `pincer/payout.py`

## Support

For questions or issues, check:

- x402 documentation: https://x402.org
- x402 GitHub: https://github.com/coinbase/x402
- Coinbase Developer Platform: https://docs.cdp.coinbase.com

---

**Built with**: Python, FastAPI, x402 SDK, SQLite, web3.py, solana-py
