# Architecture

Pincer enables a seamless value exchange between AI agents and service providers.

## Protocol Flow

The core interaction follows the **Request-Pay-Verify-Rebate** cycle.

```mermaid
sequenceDiagram
    participant User
    participant Agent as AI Agent (Client)
    participant Server as Resource Server
    participant Blockchain
    participant Sponsor

    User->>Agent: Request "Best Pizza NYC"
    Agent->>Server: GET /recommendations
    Server-->>Agent: 402 Payment Required
    Note right of Server: x402 Header: <br/>"pay 0.01 USDC to addr..."

    Agent->>Blockchain: Sign & Broadcast Tx
    Blockchain-->>Agent: Confirmed

    Agent->>Server: Retry Request + Proof
    Server->>Blockchain: Verify Transaction
    Blockchain-->>Server: Defines Success

    Server-->>Agent: 200 OK + Data
    Note right of Server: Returns Recommendations<br/>+ Sponsor Rebate Offer

    rect rgb(240, 248, 255)
    Note over Sponsor, Blockchain: Async / Post-Process
    Sponsor->>Blockchain: Detects Tx & Refunds User
    Blockchain-->>User: +0.01 USDC (Rebate)
    end
```

## Key Components

### 1. Resource Server (`x402-server`)

The gatekeeper. It intercepts requests, checks for valid payment headers, and issues 402 challenges if payment is missing. In Pincer, this is wrapped by `PincerResourceServer` for simpler integration.

### 2. Facilitator (Verified by Pincer)

An on-chain or off-chain entity that verifies the payment occurred. Pincer acts as a facilitator, indexing blockchain events to confirm transactions instantly.

### 3. Sponsors

Third-party entities (like Restaurants, Brands) that configure "Campaigns". If a user's request matches a campaign criteria (e.g., "User paid for Pizza search"), the sponsor triggers a rebate transaction to the user's wallet.
