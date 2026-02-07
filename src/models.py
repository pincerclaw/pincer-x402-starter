"""Shared data models for Pincer x402 demo.

All Pydantic models used across services for type safety and validation.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SponsorCampaign(BaseModel):
    """Sponsor campaign configuration."""

    campaign_id: str = Field(description="Unique campaign identifier")
    merchant_name: str = Field(description="Merchant display name")
    offer_text: str = Field(description="Offer description shown to users")
    rebate_amount_usd: float = Field(description="Rebate amount in USD")
    total_budget_usd: float = Field(description="Total campaign budget in USD")
    remaining_budget_usd: float = Field(description="Remaining budget in USD")
    active: bool = Field(default=True, description="Whether campaign is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SponsoredOffer(BaseModel):
    """Sponsored offer attached to paywalled content response."""

    sponsor_id: str = Field(description="Campaign/sponsor identifier")
    merchant_name: str = Field(description="Merchant display name")
    offer_text: str = Field(description="Offer description")
    rebate_amount: str = Field(description="Rebate amount formatted (e.g., '$5.00')")
    merchant_url: str = Field(description="URL to merchant checkout")
    session_id: str = Field(description="Payment session ID for tracking")
    offer_id: str = Field(description="Unique offer instance ID")


class PaymentSession(BaseModel):
    """Track verified x402 payment sessions."""

    session_id: str = Field(description="Unique session identifier")
    user_address: str = Field(description="User wallet address that paid")
    network: str = Field(description="Network identifier (e.g., eip155:84532)")
    amount_paid_usd: float = Field(description="Amount paid in USD")
    payment_hash: Optional[str] = Field(default=None, description="Transaction hash")
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    rebate_settled: bool = Field(default=False, description="Whether rebate has been settled")
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for tracing")


class ConversionWebhook(BaseModel):
    """Webhook payload from merchant for conversion tracking."""

    webhook_id: str = Field(description="Unique webhook identifier for idempotency")
    session_id: str = Field(description="Payment session ID from offer")
    user_address: str = Field(description="User wallet address")
    purchase_amount_usd: float = Field(description="Purchase amount in USD")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    merchant_id: Optional[str] = Field(default=None, description="Merchant identifier")


class WebhookRecord(BaseModel):
    """Database record for webhook processing tracking."""

    webhook_id: str = Field(description="Unique webhook identifier")
    session_id: str
    user_address: str
    status: Literal["processing", "completed", "failed"] = Field(default="processing")
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    rebate_tx_hash: Optional[str] = Field(default=None, description="Rebate transaction hash")


class RebateSettlement(BaseModel):
    """Rebate settlement record."""

    settlement_id: str = Field(description="Unique settlement identifier")
    session_id: str = Field(description="Payment session ID")
    webhook_id: str = Field(description="Webhook that triggered settlement")
    user_address: str = Field(description="User receiving rebate")
    rebate_amount_usd: float = Field(description="Rebate amount in USD")
    network: str = Field(description="Network for rebate payment")
    tx_hash: Optional[str] = Field(default=None, description="Rebate transaction hash")
    status: Literal["pending", "confirmed", "failed"] = Field(default="pending")
    campaign_id: str = Field(description="Campaign that provided rebate")
    settled_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = Field(default=None)
    correlation_id: Optional[str] = Field(default=None)


class PaymentVerificationRequest(BaseModel):
    """Request to verify x402 payment."""

    session_id: str
    payment_signature: str
    payment_requirements: dict


class PaymentVerificationResponse(BaseModel):
    """Response from payment verification."""

    verified: bool
    session_id: str
    user_address: Optional[str] = None
    network: Optional[str] = None
    amount_usd: Optional[float] = None
    error: Optional[str] = None


class OfferGenerationRequest(BaseModel):
    """Request to generate sponsored offers for a verified session."""

    session_id: str
    user_address: str
    network: str
    amount_paid_usd: float
    correlation_id: Optional[str] = None


class OfferGenerationResponse(BaseModel):
    """Response containing generated offers."""

    offers: list[SponsoredOffer]
    session_id: str
