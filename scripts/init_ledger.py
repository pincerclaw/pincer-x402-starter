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
    # Initialize campaigns from JSON
    await db.initialize_campaigns()

    # Verify campaigns were created
    campaigns = await db.get_active_campaigns()
    if campaigns:
        logger.info(f"Initialized {len(campaigns)} campaigns successfully.")
        for campaign in campaigns:
            logger.info(f"- {campaign.campaign_id}: {campaign.merchant_name} (${campaign.budget_remaining:.2f})")
    else:
        logger.error("Failed to initialize campaigns or no active campaigns found.")
        sys.exit(1)

    logger.info("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
