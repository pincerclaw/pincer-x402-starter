"""Unit tests for sponsor budget management."""

import pytest
import sqlite3
from datetime import datetime

from src.database import Database
from src.models import SponsorCampaign


@pytest.mark.unit
class TestBudgetManagement:
    """Test campaign budget operations."""

    @pytest.fixture
    async def test_db(self, tmp_path):
        """Create a temporary test database and seed a campaign."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.initialize()
        
        # Manually insert a test campaign
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO campaigns 
                (campaign_id, merchant_name, offer_text, 
                 rebate_amount, rebate_asset, rebate_network,
                 budget_total, budget_remaining, budget_asset,
                 active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "shake-shack-promo",
                    "Shake Shack",
                    "Get 15% off",
                    5.00,
                    "USDC",
                    "solana:devnet",
                    100.00,
                    100.00,
                    "USDC",
                    1,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            await conn.commit()
            
        return db

    @pytest.mark.asyncio
    async def test_budget_reservation_success(self, test_db):
        """Test successful budget reservation when funds available."""
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign is not None

        initial_budget = campaign.budget_remaining
        reserve_amount = 5.00

        # Reserve budget
        success = await test_db.reserve_budget("shake-shack-promo", reserve_amount)
        assert success is True

        # Check budget was deducted
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.budget_remaining == initial_budget - reserve_amount

    @pytest.mark.asyncio
    async def test_budget_reservation_insufficient_funds(self, test_db):
        """Test budget reservation fails when insufficient funds."""
        campaign = await test_db.get_campaign("shake-shack-promo")
        initial_budget = campaign.budget_remaining

        # Try to reserve more than available
        excessive_amount = initial_budget + 10.00

        success = await test_db.reserve_budget("shake-shack-promo", excessive_amount)
        assert success is False

        # Budget should remain unchanged
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.budget_remaining == initial_budget

    @pytest.mark.asyncio
    async def test_multiple_reservations(self, test_db):
        """Test multiple budget reservations."""
        campaign = await test_db.get_campaign("shake-shack-promo")
        initial_budget = campaign.budget_remaining

        # Make multiple reservations
        await test_db.reserve_budget("shake-shack-promo", 5.00)
        await test_db.reserve_budget("shake-shack-promo", 5.00)
        await test_db.reserve_budget("shake-shack-promo", 5.00)

        # Check total deduction
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.budget_remaining == initial_budget - 15.00

    @pytest.mark.asyncio
    async def test_budget_reservation_inactive_campaign(self, test_db):
        """Test that inactive campaigns cannot reserve budget."""
        # Deactivate campaign
        import aiosqlite
        async with aiosqlite.connect(test_db.db_path) as conn:
            await conn.execute("UPDATE campaigns SET active = 0 WHERE campaign_id = ?", ("shake-shack-promo",))
            await conn.commit()

        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.active is False
        
        success = await test_db.reserve_budget("shake-shack-promo", 5.00)
        assert success is False
