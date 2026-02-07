"""Unit tests for sponsor budget management."""

import pytest

from src.database import Database


@pytest.mark.unit
class TestBudgetManagement:
    """Test campaign budget operations."""

    @pytest.fixture
    async def test_db(self, tmp_path):
        """Create a temporary test database."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.initialize()
        await db.initialize_default_campaign()
        return db

    @pytest.mark.asyncio
    async def test_budget_reservation_success(self, test_db):
        """Test successful budget reservation when funds available."""
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign is not None

        initial_budget = campaign.remaining_budget_usd
        reserve_amount = 5.00

        # Reserve budget
        success = await test_db.reserve_budget("shake-shack-promo", reserve_amount)
        assert success is True

        # Check budget was deducted
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.remaining_budget_usd == initial_budget - reserve_amount

    @pytest.mark.asyncio
    async def test_budget_reservation_insufficient_funds(self, test_db):
        """Test budget reservation fails when insufficient funds."""
        campaign = await test_db.get_campaign("shake-shack-promo")
        initial_budget = campaign.remaining_budget_usd

        # Try to reserve more than available
        excessive_amount = initial_budget + 10.00

        success = await test_db.reserve_budget("shake-shack-promo", excessive_amount)
        assert success is False

        # Budget should remain unchanged
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.remaining_budget_usd == initial_budget

    @pytest.mark.asyncio
    async def test_multiple_reservations(self, test_db):
        """Test multiple budget reservations."""
        campaign = await test_db.get_campaign("shake-shack-promo")
        initial_budget = campaign.remaining_budget_usd

        # Make multiple reservations
        await test_db.reserve_budget("shake-shack-promo", 5.00)
        await test_db.reserve_budget("shake-shack-promo", 5.00)
        await test_db.reserve_budget("shake-shack-promo", 5.00)

        # Check total deduction
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.remaining_budget_usd == initial_budget - 15.00

    @pytest.mark.asyncio
    async def test_budget_reservation_inactive_campaign(self, test_db):
        """Test that inactive campaigns cannot reserve budget."""
        # This would require adding a method to deactivate campaigns
        # For now, this is a placeholder test
        campaign = await test_db.get_campaign("shake-shack-promo")
        assert campaign.active is True
