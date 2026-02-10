"""Pydantic models for Pincer SDK."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Coupon(BaseModel):
    """Coupon details for a sponsored offer."""
    code: str
    discount_amount: float
    discount_type: str  # "percentage" or "fixed"
    description: str


class SponsoredOffer(BaseModel):
    """Sponsored offer details returned by Pincer."""
    sponsor_id: str
    merchant_name: str
    offer_text: str
    rebate_amount: float
    rebate_asset: str
    rebate_network: str
    coupons: List[Coupon] = []
    checkout_url: str
    session_id: str
    offer_id: str


class ConversionEvent(BaseModel):
    """Conversion event data to be sent to Pincer."""
    session_id: str
    user_address: str
    purchase_amount: float
    purchase_asset: str = "USD"
    merchant_id: Optional[str] = None
    timestamp: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ConversionResponse(BaseModel):
    """Response from reporting a conversion."""
    status: str
    webhook_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
