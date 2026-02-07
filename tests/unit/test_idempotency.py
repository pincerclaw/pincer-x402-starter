"""Unit tests for idempotency logic (webhook deduplication)."""

import pytest

from src.database import Database
from src.models import WebhookRecord


@pytest.mark.unit
class TestIdempotency:
    """Test webhook idempotency guarantees."""

    @pytest.fixture
    async def test_db(self, tmp_path):
        """Create a temporary test database."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.initialize()
        await db.initialize_default_campaign()
        return db

    @pytest.mark.asyncio
    async def test_duplicate_webhook_rejected(self, test_db):
        """Test that duplicate webhook IDs are rejected."""
        webhook = WebhookRecord(
            webhook_id="wh-test-123",
            session_id="sess-test",
            user_address="0x123",
            status="processing",
        )

        # First create should succeed
        created1 = await test_db.create_webhook_record(webhook)
        assert created1 is True

        # Second create with same webhook_id should fail
        created2 = await test_db.create_webhook_record(webhook)
        assert created2 is False

    @pytest.mark.asyncio
    async def test_webhook_status_idempotent_return(self, test_db):
        """Test that completed webhooks return previous result."""
        webhook = WebhookRecord(
            webhook_id="wh-test-456",
            session_id="sess-test",
            user_address="0x456",
            status="processing",
        )

        await test_db.create_webhook_record(webhook)

        # Update to completed with tx hash
        await test_db.update_webhook_status(
            "wh-test-456",
            "completed",
            rebate_tx_hash="0xabcdef",
        )

        # Retrieve webhook
        retrieved = await test_db.get_webhook_record("wh-test-456")

        assert retrieved is not None
        assert retrieved.status == "completed"
        assert retrieved.rebate_tx_hash == "0xabcdef"
        assert retrieved.processed_at is not None

    @pytest.mark.asyncio
    async def test_multiple_different_webhooks(self, test_db):
        """Test that different webhook IDs are allowed."""
        webhook1 = WebhookRecord(
            webhook_id="wh-test-001",
            session_id="sess-test",
            user_address="0x123",
            status="processing",
        )

        webhook2 = WebhookRecord(
            webhook_id="wh-test-002",
            session_id="sess-test",
            user_address="0x123",
            status="processing",
        )

        # Both should succeed
        created1 = await test_db.create_webhook_record(webhook1)
        created2 = await test_db.create_webhook_record(webhook2)

        assert created1 is True
        assert created2 is True
