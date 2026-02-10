"""Utility functions for Pincer SDK."""

import hashlib
import hmac


def create_webhook_signature(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for webhook payload.

    Args:
        payload: The JSON payload string.
        secret: The webhook secret key.

    Returns:
        The hex-encoded HMAC signature.
    """
    if not secret:
        raise ValueError("Webhook secret is required for signing")
        
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
