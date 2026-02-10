# Pincer Protocol

[![Colosseum Agent Hackathon](https://img.shields.io/badge/Colosseum-Agent%20Hackathon-purple)](https://colosseum.com/agent-hackathon/projects/pincer-ad-protocol-for-ai-agents)

**The Intelligent Payment-Gated API Layer**

Pincer represents a new paradigm in API monetization: **Payment-Gated Intelligence**. It seamlessly integrates high-performance AI agents with the x402 payment protocol, allowing developers to monetize their APIs with micro-transactions while offering automated rebates and sponsored access.

[Product Demo](https://pincer-web.pages.dev/){ .md-button .md-button--primary }
[Pitch Deck](https://pincer-pitch.pages.dev){ .md-button }

## Why Pincer?

### 🚀 Zero-Friction Monetization

Integrate payments into any API endpoint with just a few lines of code. No complex merchant accounts or subscription management required.

### 🤖 Agent-Native

Built for the autonomous economy. Pincer APIs are designed to be consumed by AI agents, with machine-readable payment requirements and automatic negotiation.

### 💸 Dynamic Rebates

Sponsors can subsidize user access. Pincer's "Post-Pay Rebate" system allows third parties to refund user fees instantly, driving traffic without lowering the paywall.

## Examples

Check out the `examples/` directory for standalone scripts demonstrating key integrations:

- [Buyer Flow](../examples/x402_buyer_flow.py): Client-side payment handling.
- [Resource Server](../examples/x402_resource_integration.py): Protecting content with x402.
- [Sponsor Integration](../examples/sponsor_integration.py): Reporting conversions.

## Architecture

Understand how Pincer facilitates trustless payments and rebates between Agents and APIs.

[:arrow_right: Core Architecture](architecture.md)

## Get Started

<div class="grid cards" markdown>

- **x402 Sellers**

  Monetize your data/services and accept crypto micro-payments from Buyers.

  [:arrow_right: Seller Integration](guides/seller.md)
  [:arrow_right: Buyer Guide](guides/buyer.md)

- **Sponsors**

  Offer rebates to users to drive traffic and brand awareness.

  [:arrow_right: Campaign Guide](guides/sponsor.md)

</div>

## See it in Action

Want to see the entire flow? Run the end-to-end demo.

[Run Demo](demo.md){ .md-button }
