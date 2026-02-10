
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.resource.server import app
from src.config import config

@pytest.fixture
def client():
    return TestClient(app)

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "resource"}

def test_recommendations_no_payment(client):
    """Test accessing protected route without payment returns 402."""
    response = client.get("/recommendations")
    assert response.status_code == 402
    assert "payment-required" in response.headers
