"""
Bobby - Langfuse Observability Integration
===========================================
Provides tracing and observability for agent nodes, LLM calls, and RAG retrieval.
Configured via .env:
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_SECRET_KEY
  LANGFUSE_HOST
"""
from __future__ import annotations
import os
import functools
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)

# Pre-populate env vars
if settings.langfuse_public_key:
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host or "https://cloud.langfuse.com"
    os.environ["LANGFUSE_BASE_URL"] = settings.langfuse_host or "https://cloud.langfuse.com"

_langfuse_client = None
_langfuse_enabled = False


def is_langfuse_enabled() -> bool:
    """Returns True if valid Langfuse credentials are configured."""
    return bool(
        settings.langfuse_public_key
        and settings.langfuse_public_key.strip()
        and "TODO" not in settings.langfuse_public_key
        and settings.langfuse_secret_key
        and settings.langfuse_secret_key.strip()
        and "TODO" not in settings.langfuse_secret_key
    )


def get_langfuse_client():
    """Returns singleton Langfuse client if configured in .env."""
    global _langfuse_client, _langfuse_enabled
    if _langfuse_client is not None:
        return _langfuse_client

    if is_langfuse_enabled():
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host or "https://cloud.langfuse.com",
            )
            _langfuse_enabled = True
            logger.info("langfuse.initialized", host=settings.langfuse_host)
            return _langfuse_client
        except Exception as e:
            logger.warning("langfuse.init_error", error=str(e))
            return None

    return None


def observe_node(name: str):
    """
    Decorator for agent nodes that applies Langfuse tracing when configured,
    or passes through cleanly when Langfuse is not enabled.
    """
    def decorator(fn):
        if is_langfuse_enabled():
            try:
                from langfuse import observe
                return observe(name=name)(fn)
            except Exception:
                pass

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)
        return wrapper

    return decorator
