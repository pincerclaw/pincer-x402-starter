"""Database initialization script.

Run this to initialize the Pincer ledger database with schema and default campaign.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.database import db
from src.logging_utils import get_logger, setup_logging

setup_logging(config.log_level, config.log_format)
logger = get_logger(__name__)


async def main():
    """Initialize the database."""
    logger.info("Initializing Pincer database...")
    logger.info(f"Database path: {db.db_path}")

    # Initialize schema
    await db.initialize()

    # Initialize default campaign
    await db.initialize_default_campaign()

    # Verify campaign was created
    campaign = await db.get_campaign(config.sponsor_campaign_id)
    if campaign:
        logger.info(f"Campaign initialized successfully:")
        logger.info(f"  ID: {campaign.campaign_id}")
        logger.info(f"  Merchant: {campaign.merchant_name}")
        logger.info(f"  Budget: ${campaign.remaining_budget_usd:.2f}")
    else:
        logger.error("Failed to initialize campaign")
        sys.exit(1)

    logger.info("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
