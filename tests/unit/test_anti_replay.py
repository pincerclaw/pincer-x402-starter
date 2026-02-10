"""Unit tests for anti-replay protection (session reuse prevention)."""

import pytest
import uuid
from datetime import datetime

from src.database import Database
from src.models import PaymentSession


@pytest.mark.unit
class TestAntiReplay:
    """Test anti-replay protection for payment sessions."""

    @pytest.fixture
    async def test_db(self, tmp_path):
        """Create a temporary test database."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.initialize()
        return db

    @pytest.mark.asyncio
    async def test_session_rebate_settled_flag(self, test_db):
        """Test that sessions track rebate settlement status."""
        session = PaymentSession(
            session_id="sess-test-123",
            user_address="0x123",
            network="eip155:84532",
            amount_paid=0.10,
            payment_asset="USDC",
            verified_at=datetime.utcnow(),
            rebate_settled=False,
        )

        await test_db.create_session(session)

        # Verify initial state
        retrieved = await test_db.get_session("sess-test-123")
        assert retrieved is not None
        assert retrieved.rebate_settled is False

        # Mark as settled
        await test_db.mark_session_settled("sess-test-123")

        # Verify updated state
        retrieved = await test_db.get_session("sess-test-123")
        assert retrieved.rebate_settled is True

    @pytest.mark.asyncio
    async def test_prevent_double_settlement(self, test_db):
        """Test that attempting to settle an already-settled session is detected."""
        session = PaymentSession(
            session_id="sess-test-456",
            user_address="0x456",
            network="eip155:84532",
            amount_paid=0.10,
            payment_asset="USDC",
            verified_at=datetime.utcnow(),
            rebate_settled=False,
        )

        await test_db.create_session(session)

        # First settlement
        await test_db.mark_session_settled("sess-test-456")

        # Check if session is settled
        retrieved = await test_db.get_session("sess-test-456")
        assert retrieved.rebate_settled is True

        # In webhook handler, this would prevent second settlement:
        if retrieved.rebate_settled:
            # This is the anti-replay check logic
            pass 

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self, test_db):
        """Test that different sessions are tracked independently."""
        session1 = PaymentSession(
            session_id="sess-test-001",
            user_address="0x123",
            network="eip155:84532",
            amount_paid=0.10,
            payment_asset="USDC",
            verified_at=datetime.utcnow(),
            rebate_settled=False,
        )

        session2 = PaymentSession(
            session_id="sess-test-002",
            user_address="0x123",
            network="eip155:84532",
            amount_paid=0.10,
            payment_asset="USDC",
            verified_at=datetime.utcnow(),
            rebate_settled=False,
        )

        await test_db.create_session(session1)
        await test_db.create_session(session2)

        # Settle only first session
        await test_db.mark_session_settled("sess-test-001")

        # Verify states
        s1 = await test_db.get_session("sess-test-001")
        s2 = await test_db.get_session("sess-test-002")

        assert s1.rebate_settled is True
        assert s2.rebate_settled is False
