"""Unit tests for webhook signature verification."""

import pytest

from src.pincer.webhooks import verify_webhook_signature


@pytest.mark.unit
class TestSignatureVerification:
    """Test HMAC-SHA256 signature verification."""

    def test_valid_signature(self):
        """Test that valid signatures pass verification."""
        payload = b'{"webhook_id":"wh-123","data":"test"}'
        secret = "my_secret_key"

        # Generate signature (simulating merchant)
        import hashlib
        import hmac

        expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Verify
        result = verify_webhook_signature(payload, expected_sig, secret)
        assert result is True

    def test_invalid_signature(self):
        """Test that invalid signatures fail verification."""
        payload = b'{"webhook_id":"wh-123","data":"test"}'
        secret = "my_secret_key"
        wrong_signature = "0" * 64  # Invalid signature

        result = verify_webhook_signature(payload, wrong_signature, secret)
        assert result is False

    def test_wrong_secret(self):
        """Test that signatures with wrong secret fail."""
        payload = b'{"webhook_id":"wh-123","data":"test"}'
        correct_secret = "my_secret_key"
        wrong_secret = "wrong_secret"

        import hashlib
        import hmac

        # Generate signature with wrong secret
        wrong_sig = hmac.new(wrong_secret.encode(), payload, hashlib.sha256).hexdigest()

        # Try to verify with correct secret
        result = verify_webhook_signature(payload, wrong_sig, correct_secret)
        assert result is False

    def test_modified_payload(self):
        """Test that modified payloads fail verification."""
        original_payload = b'{"webhook_id":"wh-123","data":"test"}'
        modified_payload = b'{"webhook_id":"wh-456","data":"modified"}'
        secret = "my_secret_key"

        import hashlib
        import hmac

        # Generate signature for original
        signature = hmac.new(secret.encode(), original_payload, hashlib.sha256).hexdigest()

        # Try to verify with modified payload
        result = verify_webhook_signature(modified_payload, signature, secret)
        assert result is False

    def test_empty_signature(self):
        """Test that empty signatures fail verification."""
        payload = b'{"webhook_id":"wh-123","data":"test"}'
        secret = "my_secret_key"
        empty_signature = ""

        result = verify_webhook_signature(payload, empty_signature, secret)
        assert result is False
