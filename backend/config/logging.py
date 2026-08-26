"""
Bobby — Logging Configuration
================================
Configures structlog for consistent JSON log output.

Call configure_logging() once at application startup in main.py.

Log levels:
  DEBUG   — detailed internal state (only in dev)
  INFO    — normal operation events (node start/complete, API calls)
  WARNING — degraded state (fallback used, rate limit hit)
  ERROR   — failed operation (caught exception, external API error)

Usage:
  import structlog
  logger = structlog.get_logger(__name__)
  logger.info("event.name", key="value", user_id="abc")
"""
from __future__ import annotations
import logging
import sys
import structlog
from config.settings import settings


def configure_logging() -> None:
    """Sets up structlog for the application. Call once at startup."""

    log_level = logging.DEBUG if settings.is_demo else logging.INFO

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Shared processors for all log entries
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_demo:
        # Human-readable output for development
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # JSON output for production (Azure Monitor / App Insights compatible)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
