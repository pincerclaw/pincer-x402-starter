"""SQLite database interface for Pincer ledger.

Manages sponsor budgets, payment sessions, webhooks, and settlements with
support for idempotency and anti-replay protection.
"""

import asyncio
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Optional

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
    rebate_amount_usd REAL NOT NULL,
    total_budget_usd REAL NOT NULL,
    remaining_budget_usd REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Payment sessions table (for anti-replay protection)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_address TEXT NOT NULL,
    network TEXT NOT NULL,
    amount_paid_usd REAL NOT NULL,
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
    rebate_amount_usd REAL NOT NULL,
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

    def __init__(self, db_path: str = None):
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

    async def initialize_default_campaign(self) -> None:
        """Initialize the default sponsor campaign from config."""
        campaign = SponsorCampaign(
            campaign_id=config.sponsor_campaign_id,
            merchant_name=config.sponsor_merchant_name,
            offer_text=config.sponsor_offer_text,
            rebate_amount_usd=config.sponsor_rebate_amount_usd,
            total_budget_usd=config.sponsor_total_budget_usd,
            remaining_budget_usd=config.sponsor_total_budget_usd,
            active=True,
            created_at=datetime.utcnow(),
        )

        async with aiosqlite.connect(self.db_path) as db:
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
                    (campaign_id, merchant_name, offer_text, rebate_amount_usd, 
                     total_budget_usd, remaining_budget_usd, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        campaign.campaign_id,
                        campaign.merchant_name,
                        campaign.offer_text,
                        campaign.rebate_amount_usd,
                        campaign.total_budget_usd,
                        campaign.remaining_budget_usd,
                        1 if campaign.active else 0,
                        campaign.created_at.isoformat(),
                        campaign.created_at.isoformat(),
                    ),
                )
                await db.commit()
                logger.info(f"Initialized campaign: {campaign.campaign_id}")
            else:
                logger.info(f"Campaign already exists: {campaign.campaign_id}")

    # Campaign operations
    async def get_campaign(self, campaign_id: str) -> Optional[SponsorCampaign]:
        """Get a sponsor campaign by ID.

        Args:
            campaign_id: Campaign identifier.

        Returns:
            SponsorCampaign if found, None otherwise.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            )
            row = await cursor.fetchone()

            if row:
                return SponsorCampaign(
                    campaign_id=row["campaign_id"],
                    merchant_name=row["merchant_name"],
                    offer_text=row["offer_text"],
                    rebate_amount_usd=row["rebate_amount_usd"],
                    total_budget_usd=row["total_budget_usd"],
                    remaining_budget_usd=row["remaining_budget_usd"],
                    active=bool(row["active"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            return None

    async def reserve_budget(self, campaign_id: str, amount: float) -> bool:
        """Reserve budget for an offer (atomic operation).

        Args:
            campaign_id: Campaign to reserve from.
            amount: Amount to reserve.

        Returns:
            True if reservation succeeded, False if insufficient budget.
        """
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Check current budget
                cursor = await db.execute(
                    "SELECT remaining_budget_usd, active FROM campaigns WHERE campaign_id = ?",
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
                    logger.warning(
                        f"Insufficient budget for {campaign_id}: "
                        f"need ${amount}, have ${remaining}"
                    )
                    return False

                # Reserve budget
                await db.execute(
                    """
                    UPDATE campaigns 
                    SET remaining_budget_usd = remaining_budget_usd - ?,
                        updated_at = ?
                    WHERE campaign_id = ?
                    """,
                    (amount, datetime.utcnow().isoformat(), campaign_id),
                )
                await db.commit()
                logger.info(f"Reserved ${amount} from campaign {campaign_id}")
                return True

    async def deduct_budget(self, campaign_id: str, amount: float) -> bool:
        """Deduct budget after settlement (should already be reserved).

        Args:
            campaign_id: Campaign to deduct from.
            amount: Amount to deduct.

        Returns:
            True if deduction succeeded.
        """
        # Budget was already reserved, so this is just for record-keeping
        # In a production system, you might separate "reserved" vs "spent" budgets
        logger.info(f"Budget already deducted during reservation for {campaign_id}: ${amount}")
        return True

    # Session operations
    async def create_session(self, session: PaymentSession) -> None:
        """Create a payment session record.

        Args:
            session: Payment session to create.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sessions 
                (session_id, user_address, network, amount_paid_usd, payment_hash,
                 verified_at, rebate_settled, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.user_address,
                    session.network,
                    session.amount_paid_usd,
                    session.payment_hash,
                    session.verified_at.isoformat(),
                    1 if session.rebate_settled else 0,
                    session.correlation_id,
                ),
            )
            await db.commit()
        logger.info(f"Created session: {session.session_id}")

    async def get_session(self, session_id: str) -> Optional[PaymentSession]:
        """Get a payment session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            PaymentSession if found, None otherwise.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

            if row:
                return PaymentSession(
                    session_id=row["session_id"],
                    user_address=row["user_address"],
                    network=row["network"],
                    amount_paid_usd=row["amount_paid_usd"],
                    payment_hash=row["payment_hash"],
                    verified_at=datetime.fromisoformat(row["verified_at"]),
                    rebate_settled=bool(row["rebate_settled"]),
                    correlation_id=row["correlation_id"],
                )
            return None

    async def mark_session_rebate_settled(self, session_id: str) -> None:
        """Mark a session as having its rebate settled (anti-replay protection).

        Args:
            session_id: Session to mark as settled.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET rebate_settled = 1 WHERE session_id = ?",
                (session_id,),
            )
            await db.commit()
        logger.info(f"Marked session as settled: {session_id}")

    # Webhook operations (idempotency)
    async def create_webhook_record(self, webhook: WebhookRecord) -> bool:
        """Create a webhook record for idempotency tracking.

        Args:
            webhook: Webhook record to create.

        Returns:
            True if record was created (first time), False if duplicate.
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
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
            logger.info(f"Created webhook record: {webhook.webhook_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Webhook already exists (idempotency): {webhook.webhook_id}")
            return False

    async def get_webhook_record(self, webhook_id: str) -> Optional[WebhookRecord]:
        """Get a webhook record by ID.

        Args:
            webhook_id: Webhook identifier.

        Returns:
            WebhookRecord if found, None otherwise.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM webhooks WHERE webhook_id = ?",
                (webhook_id,),
            )
            row = await cursor.fetchone()

            if row:
                return WebhookRecord(
                    webhook_id=row["webhook_id"],
                    session_id=row["session_id"],
                    user_address=row["user_address"],
                    status=row["status"],
                    received_at=datetime.fromisoformat(row["received_at"]),
                    processed_at=(
                        datetime.fromisoformat(row["processed_at"])
                        if row["processed_at"]
                        else None
                    ),
                    error_message=row["error_message"],
                    rebate_tx_hash=row["rebate_tx_hash"],
                )
            return None

    async def update_webhook_status(
        self,
        webhook_id: str,
        status: str,
        error_message: Optional[str] = None,
        rebate_tx_hash: Optional[str] = None,
    ) -> None:
        """Update webhook processing status.

        Args:
            webhook_id: Webhook to update.
            status: New status (processing, completed, failed).
            error_message: Error message if failed.
            rebate_tx_hash: Transaction hash if settled.
        """
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
                    error_message,
                    rebate_tx_hash,
                    webhook_id,
                ),
            )
            await db.commit()
        logger.info(f"Updated webhook {webhook_id} status to {status}")

    # Settlement operations
    async def create_settlement(self, settlement: RebateSettlement) -> None:
        """Create a settlement record.

        Args:
            settlement: Settlement to create.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO settlements 
                (settlement_id, session_id, webhook_id, user_address, rebate_amount_usd,
                 network, tx_hash, status, campaign_id, settled_at, confirmed_at, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    settlement.settlement_id,
                    settlement.session_id,
                    settlement.webhook_id,
                    settlement.user_address,
                    settlement.rebate_amount_usd,
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
        logger.info(f"Created settlement: {settlement.settlement_id}")

    async def update_settlement_status(
        self,
        settlement_id: str,
        status: str,
        tx_hash: Optional[str] = None,
    ) -> None:
        """Update settlement status.

        Args:
            settlement_id: Settlement to update.
            status: New status (pending, confirmed, failed).
            tx_hash: Transaction hash if available.
        """
        async with aiosqlite.connect(self.db_path) as db:
            confirmed_at = datetime.utcnow().isoformat() if status == "confirmed" else None
            await db.execute(
                """
                UPDATE settlements 
                SET status = ?, tx_hash = ?, confirmed_at = ?
                WHERE settlement_id = ?
                """,
                (status, tx_hash, confirmed_at, settlement_id),
            )
            await db.commit()
        logger.info(f"Updated settlement {settlement_id} status to {status}")


# Global database instance
db = Database()
