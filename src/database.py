"""SQLite database interface for Pincer ledger.

Manages sponsor budgets, payment sessions, webhooks, and settlements with
support for idempotency and anti-replay protection.
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from typing import List, Optional

import aiosqlite

from .config import config
from .logging_utils import get_logger
from .models import (
    PaymentSession,
    RebateSettlement,
    SponsorCampaign,
    WebhookRecord,
)

logger = get_logger(__name__)

# SQL Schema
SCHEMA_SQL = """
-- Sponsor campaigns table
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    merchant_name TEXT NOT NULL,
    offer_text TEXT NOT NULL,
    
    rebate_amount REAL NOT NULL,
    rebate_asset TEXT NOT NULL,
    rebate_network TEXT NOT NULL,
    
    budget_total REAL NOT NULL,
    budget_remaining REAL NOT NULL,
    budget_asset TEXT NOT NULL,
    
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Payment sessions table (for anti-replay protection)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_address TEXT NOT NULL,
    network TEXT NOT NULL,
    
    amount_paid REAL NOT NULL,
    payment_asset TEXT NOT NULL,
    
    payment_hash TEXT,
    verified_at TEXT NOT NULL,
    rebate_settled INTEGER NOT NULL DEFAULT 0,
    correlation_id TEXT
);

-- Webhook tracking table (for idempotency)
CREATE TABLE IF NOT EXISTS webhooks (
    webhook_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_address TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed')),
    received_at TEXT NOT NULL,
    processed_at TEXT,
    error_message TEXT,
    rebate_tx_hash TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Settlement records table
CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    webhook_id TEXT NOT NULL,
    user_address TEXT NOT NULL,
    
    rebate_amount REAL NOT NULL,
    rebate_asset TEXT NOT NULL,
    
    network TEXT NOT NULL,
    tx_hash TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'confirmed', 'failed')),
    campaign_id TEXT NOT NULL,
    settled_at TEXT NOT NULL,
    confirmed_at TEXT,
    correlation_id TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (webhook_id) REFERENCES webhooks(webhook_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sessions_user_address ON sessions(user_address);
CREATE INDEX IF NOT EXISTS idx_sessions_rebate_settled ON sessions(rebate_settled);
CREATE INDEX IF NOT EXISTS idx_webhooks_session_id ON webhooks(session_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_status ON webhooks(status);
CREATE INDEX IF NOT EXISTS idx_settlements_session_id ON settlements(session_id);
CREATE INDEX IF NOT EXISTS idx_settlements_webhook_id ON settlements(webhook_id);
"""


class Database:
    """Async database interface for Pincer ledger."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to config.database_path.
        """
        self.db_path = db_path or config.database_path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def initialize_campaigns(self) -> None:
        """Initialize sponsor campaigns from JSON config."""
        try:
            with open(config.sponsor_data_path, "r") as f:
                campaigns_data = json.load(f)
            
            async with aiosqlite.connect(self.db_path) as db:
                for data in campaigns_data:
                    # Convert JSON to model
                    campaign = SponsorCampaign(
                        campaign_id=data["id"],
                        merchant_name=data["merchant_name"],
                        offer_text=data["offer_text"],
                        rebate_amount=data["rebate"]["amount"],
                        rebate_asset=data["rebate"]["asset"],
                        rebate_network=data["rebate"]["network"],
                        budget_total=data["budget"]["total"],
                        budget_remaining=data["budget"]["remaining"],
                        budget_asset=data["budget"]["asset"],
                        active=True,
                        created_at=datetime.utcnow(),
                    )

                    # Check if campaign already exists
                    cursor = await db.execute(
                        "SELECT campaign_id FROM campaigns WHERE campaign_id = ?",
                        (campaign.campaign_id,),
                    )
                    exists = await cursor.fetchone()

                    if not exists:
                        await db.execute(
                            """
                            INSERT INTO campaigns 
                            (campaign_id, merchant_name, offer_text, 
                             rebate_amount, rebate_asset, rebate_network,
                             budget_total, budget_remaining, budget_asset,
                             active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                campaign.campaign_id,
                                campaign.merchant_name,
                                campaign.offer_text,
                                campaign.rebate_amount,
                                campaign.rebate_asset,
                                campaign.rebate_network,
                                campaign.budget_total,
                                campaign.budget_remaining,
                                campaign.budget_asset,
                                1 if campaign.active else 0,
                                campaign.created_at.isoformat(),
                                datetime.utcnow().isoformat(),
                            ),
                        )
                        logger.info(f"Initialized campaign: {campaign.campaign_id}")
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to initialize campaigns: {e}")

    async def get_campaign(self, campaign_id: str) -> Optional[SponsorCampaign]:
        """Get sponsor campaign by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return SponsorCampaign(
                        campaign_id=row["campaign_id"],
                        merchant_name=row["merchant_name"],
                        offer_text=row["offer_text"],
                        rebate_amount=row["rebate_amount"],
                        rebate_asset=row["rebate_asset"],
                        rebate_network=row["rebate_network"],
                        budget_total=row["budget_total"],
                        budget_remaining=row["budget_remaining"],
                        budget_asset=row["budget_asset"],
                        active=bool(row["active"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
        return None

    async def get_active_campaigns(self) -> List[SponsorCampaign]:
        """Get all active campaigns with sufficient budget."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM campaigns WHERE active = 1 AND budget_remaining >= rebate_amount"
            ) as cursor:
                rows = await cursor.fetchall()
                campaigns = []
                for row in rows:
                    campaigns.append(
                        SponsorCampaign(
                            campaign_id=row["campaign_id"],
                            merchant_name=row["merchant_name"],
                            offer_text=row["offer_text"],
                            rebate_amount=row["rebate_amount"],
                            rebate_asset=row["rebate_asset"],
                            rebate_network=row["rebate_network"],
                            budget_total=row["budget_total"],
                            budget_remaining=row["budget_remaining"],
                            budget_asset=row["budget_asset"],
                            active=bool(row["active"]),
                            created_at=datetime.fromisoformat(row["created_at"]),
                        )
                    )
                return campaigns

    async def reserve_budget(self, campaign_id: str, amount: float) -> bool:
        """Reserve budget for a campaign (deduct from remaining).
        
        Args:
            campaign_id: Campaign ID.
            amount: Amount to deduct.
            
        Returns:
            True if budget was reserved, False if insufficient budget.
        """
        async with self._lock:  # Simple mutex for budget updates
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT budget_remaining, active FROM campaigns WHERE campaign_id = ?",
                    (campaign_id,),
                )
                row = await cursor.fetchone()
                
                if not row:
                    logger.warning(f"Campaign not found: {campaign_id}")
                    return False
                    
                remaining, active = row
                
                if not active:
                    logger.warning(f"Campaign inactive: {campaign_id}")
                    return False
                    
                if remaining < amount:
                    logger.warning(f"Insufficient budget for {campaign_id}: {remaining} < {amount}")
                    return False
                
                # Deduct budget
                await db.execute(
                    """
                    UPDATE campaigns 
                    SET budget_remaining = budget_remaining - ?, updated_at = ?
                    WHERE campaign_id = ?
                    """,
                    (amount, datetime.utcnow().isoformat(), campaign_id),
                )
                await db.commit()
                return True

    async def create_session(self, session: PaymentSession) -> None:
        """Create a new payment session record."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO sessions 
                    (session_id, user_address, network, amount_paid, payment_asset,
                     payment_hash, verified_at, rebate_settled, correlation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        session.user_address,
                        session.network,
                        session.amount_paid,
                        session.payment_asset,
                        session.payment_hash,
                        session.verified_at.isoformat(),
                        1 if session.rebate_settled else 0,
                        session.correlation_id,
                    ),
                )
                await db.commit()
            except sqlite3.IntegrityError:
                logger.warning(f"Session already exists: {session.session_id}")

    async def get_session(self, session_id: str) -> Optional[PaymentSession]:
        """Get payment session by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return PaymentSession(
                        session_id=row["session_id"],
                        user_address=row["user_address"],
                        network=row["network"],
                        amount_paid=row["amount_paid"],
                        payment_asset=row["payment_asset"],
                        payment_hash=row["payment_hash"],
                        verified_at=datetime.fromisoformat(row["verified_at"]),
                        rebate_settled=bool(row["rebate_settled"]),
                        correlation_id=row["correlation_id"],
                    )
        return None

    async def mark_session_settled(self, session_id: str) -> None:
        """Mark a session as having its rebate settled."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET rebate_settled = 1 WHERE session_id = ?",
                (session_id,),
            )
            await db.commit()

    async def create_webhook(self, webhook: WebhookRecord) -> None:
        """Create a new webhook tracking record."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO webhooks 
                    (webhook_id, session_id, user_address, status, received_at, 
                     processed_at, error_message, rebate_tx_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        webhook.webhook_id,
                        webhook.session_id,
                        webhook.user_address,
                        webhook.status,
                        webhook.received_at.isoformat(),
                        webhook.processed_at.isoformat() if webhook.processed_at else None,
                        webhook.error_message,
                        webhook.rebate_tx_hash,
                    ),
                )
                await db.commit()
            except sqlite3.IntegrityError:
                logger.warning(f"Webhook already exists: {webhook.webhook_id}")

    async def get_webhook(self, webhook_id: str) -> Optional[WebhookRecord]:
        """Get webhook record by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM webhooks WHERE webhook_id = ?", (webhook_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return WebhookRecord(
                        webhook_id=row["webhook_id"],
                        session_id=row["session_id"],
                        user_address=row["user_address"],
                        status=row["status"],
                        received_at=datetime.fromisoformat(row["received_at"]),
                        processed_at=datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None,
                        error_message=row["error_message"],
                        rebate_tx_hash=row["rebate_tx_hash"],
                    )
        return None

    async def update_webhook_status(self, webhook_id: str, status: str, error: Optional[str] = None, tx_hash: Optional[str] = None) -> None:
        """Update webhook status."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE webhooks 
                SET status = ?, processed_at = ?, error_message = ?, rebate_tx_hash = ?
                WHERE webhook_id = ?
                """,
                (
                    status,
                    datetime.utcnow().isoformat(),
                    error,
                    tx_hash,
                    webhook_id,
                ),
            )
            await db.commit()

    async def create_settlement(self, settlement: RebateSettlement) -> None:
        """Create a new settlement record."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO settlements 
                (settlement_id, session_id, webhook_id, user_address, 
                 rebate_amount, rebate_asset, network, tx_hash, status, 
                 campaign_id, settled_at, confirmed_at, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    settlement.settlement_id,
                    settlement.session_id,
                    settlement.webhook_id,
                    settlement.user_address,
                    settlement.rebate_amount,
                    settlement.rebate_asset,
                    settlement.network,
                    settlement.tx_hash,
                    settlement.status,
                    settlement.campaign_id,
                    settlement.settled_at.isoformat(),
                    settlement.confirmed_at.isoformat() if settlement.confirmed_at else None,
                    settlement.correlation_id,
                ),
            )
            await db.commit()

    async def update_settlement_status(self, settlement_id: str, status: str, tx_hash: Optional[str] = None) -> None:
        """Update settlement status."""
        async with aiosqlite.connect(self.db_path) as db:
            updates = ["status = ?", "confirmed_at = ?"]
            params = [status, datetime.utcnow().isoformat()]
            
            if tx_hash:
                updates.append("tx_hash = ?")
                params.append(tx_hash)
                
            params.append(settlement_id)
            
            await db.execute(
                f"UPDATE settlements SET {', '.join(updates)} WHERE settlement_id = ?",
                tuple(params),
            )
            await db.commit()


# Global database instance
db = Database()
