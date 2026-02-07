"""Correlation ID based logging utilities for end-to-end tracing.

Provides structured logging with correlation IDs to trace a single user journey
across all services.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable to store correlation ID for the current request/task
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record.

        Args:
            record: The log record to filter.

        Returns:
            Always True to allow the record through.
        """
        record.correlation_id = correlation_id_var.get() or "no-correlation-id"
        return True


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_format: Log format (json or text).
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    # Set format
    if log_format == "json":
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"correlation_id": "%(correlation_id)s", "name": "%(name)s", '
            '"message": "%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s: %(message)s"
        )

    handler.setFormatter(formatter)

    # Add correlation ID filter
    handler.addFilter(CorrelationIdFilter())

    logger.addHandler(handler)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set.
    """
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID.

    Returns:
        The current correlation ID or None if not set.
    """
    return correlation_id_var.get()


def generate_correlation_id() -> str:
    """Generate a new correlation ID.

    Returns:
        A new UUID-based correlation ID.
    """
    return f"corr-{uuid.uuid4().hex[:12]}"


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: The logger name (typically __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


class CorrelationIdContext:
    """Context manager for setting correlation ID in a block of code."""

    def __init__(self, correlation_id: Optional[str] = None):
        """Initialize the context manager.

        Args:
            correlation_id: The correlation ID to set. If None, generates a new one.
        """
        self.correlation_id = correlation_id or generate_correlation_id()
        self.previous_correlation_id: Optional[str] = None

    def __enter__(self) -> str:
        """Enter the context and set the correlation ID.

        Returns:
            The correlation ID being used.
        """
        self.previous_correlation_id = get_correlation_id()
        set_correlation_id(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and restore the previous correlation ID.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.
        """
        if self.previous_correlation_id:
            set_correlation_id(self.previous_correlation_id)
        else:
            correlation_id_var.set(None)
