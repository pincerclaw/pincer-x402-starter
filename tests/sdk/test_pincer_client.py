"""Unit tests for PincerClient."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pincer_sdk.client import PincerClient

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock:
        yield mock

@pytest.mark.asyncio
async def test_report_conversion_success(mock_httpx_client):
    """Test successful conversion reporting."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success"
    }
    
    # Mock the client instance returned by AsyncClient()
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    
    # Configure the mock class to return our instance
    mock_httpx_client.return_value = mock_client_instance

    # Initialize client with webhook_secret (required for reporting)
    client = PincerClient(
        base_url="http://test.pincer",
        webhook_secret="test_secret"
    )
    
    response = await client.report_conversion(
        session_id="sess-123",
        user_address="0xUser",
        purchase_amount=100.0,
        merchant_id="merch-123"
    )
    
    assert response.status == "success"
    assert response.webhook_id is not None
    
    # Verify arguments passed to post
    mock_client_instance.post.assert_called_once()
    args, kwargs = mock_client_instance.post.call_args
    assert args[0] == "/webhooks/conversion"
    assert "X-Webhook-Signature" in kwargs["headers"]

@pytest.mark.asyncio
async def test_report_conversion_missing_secret(mock_httpx_client):
    """Test error when webhook_secret is missing."""
    client = PincerClient(base_url="http://test.pincer")
    # No secret provided
    
    with pytest.raises(ValueError, match="webhook_secret is required"):
        await client.report_conversion(
            session_id="sess-123",
            user_address="0xUser",
            purchase_amount=100.0
        )

@pytest.mark.asyncio
async def test_report_conversion_server_error(mock_httpx_client):
    """Test handling of server errors."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = PincerClient(
        base_url="http://test.pincer",
        webhook_secret="test_secret"
    )
    
    response = await client.report_conversion(
        session_id="sess-123",
        user_address="0xUser",
        purchase_amount=100.0
    )
    
    assert response.status == "error"
    assert "Failed to report conversion: 500" in response.error
