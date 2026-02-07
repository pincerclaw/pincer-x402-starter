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
    
    # Rebate (x402 fee subsidy)
    rebate_amount: float = Field(description="Rebate amount")
    rebate_asset: str = Field(description="Rebate asset symbol (e.g. USDC)")
    rebate_network: str = Field(description="Rebate network (e.g. solana:...)")
    
    # Budget
    budget_total: float = Field(description="Total campaign budget")
    budget_remaining: float = Field(description="Remaining budget")
    budget_asset: str = Field(description="Budget asset symbol")
    
    coupons: list["Coupon"] = Field(default_factory=list, description="Discount coupons")
    
    active: bool = Field(default=True, description="Whether campaign is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Coupon(BaseModel):
    """Discount coupon from sponsor."""

    code: str = Field(description="Coupon code (e.g., 'SHAKE15')")
    description: str = Field(description="Coupon description (e.g., '15% off entire order')")
    discount_type: Literal["percentage", "fixed"] = Field(description="Type of discount")
    discount_value: float = Field(description="Discount value (15.0 means 15% or $15)")


class SponsoredOffer(BaseModel):
    """Sponsored offer attached to paywalled content response."""

    sponsor_id: str = Field(description="Campaign/sponsor identifier")
    merchant_name: str = Field(description="Merchant display name")
    offer_text: str = Field(description="Offer description")

    # Rebate = x402 fee subsidy (paid to agent after purchase)
    rebate_amount: float = Field(description="Rebate amount in token units")
    rebate_asset: str = Field(description="Token for rebate (e.g., 'USDC')")
    rebate_network: str = Field(description="Network for rebate (e.g., 'solana:EtWTRABZ...')")

    # Coupons = merchant discounts (auto-applied via checkout_url)
    coupons: list[Coupon] = Field(default_factory=list, description="Discount coupons")

    # Trackable checkout link (session embedded for attribution)
    checkout_url: str = Field(description="Checkout URL with session tracking")

    session_id: str = Field(description="Payment session ID for tracking")
    offer_id: str = Field(description="Unique offer instance ID")



class PaymentSession(BaseModel):
    """Track verified x402 payment sessions."""

    session_id: str = Field(description="Unique session identifier")
    user_address: str = Field(description="User wallet address that paid")
    network: str = Field(description="Network identifier (e.g., eip155:84532)")
    
    amount_paid: float = Field(description="Amount paid")
    payment_asset: str = Field(default="USDC", description="Asset used for payment")
    
    payment_hash: Optional[str] = Field(default=None, description="Transaction hash")
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    rebate_settled: bool = Field(default=False, description="Whether rebate has been settled")
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for tracing")


class ConversionWebhook(BaseModel):
    """Webhook payload from merchant for conversion tracking."""

    webhook_id: str = Field(description="Unique webhook identifier for idempotency")
    session_id: str = Field(description="Payment session ID from offer")
    user_address: str = Field(description="User wallet address")
    
    purchase_amount: float = Field(description="Purchase amount")
    purchase_asset: str = Field(default="USD", description="Purchase currency")
    
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
    
    rebate_amount: float = Field(description="Rebate amount")
    rebate_asset: str = Field(description="Rebate asset symbol")
    
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
    payment_payload: dict = Field(description="x402 payment payload")
    payment_requirements: dict = Field(description="x402 payment requirements")


class PaymentVerificationResponse(BaseModel):
    """Response from payment verification."""

    verified: bool
    session_id: str
    user_address: Optional[str] = None
    network: Optional[str] = None
    amount: Optional[float] = None
    sponsors: list[SponsoredOffer] = Field(default_factory=list, description="Sponsors (offers) unlocked by payment")
    error: Optional[str] = None

