"""
Bobby — Supabase Client
========================
Wraps Supabase-py for database operations in demo mode.
Handles: auth, table reads/writes, vector search via RPC.

Usage:
  from integrations.supabase_client import get_supabase_client
  sb = get_supabase_client()
  data = sb.table("tickets").select("*").execute()
"""
from __future__ import annotations
import structlog
from supabase import create_client, Client
from config.settings import settings

logger = structlog.get_logger(__name__)

_supabase_instance: Client | None = None


def get_supabase_client() -> Client:
    """Returns a singleton Supabase client (demo mode only)."""
    global _supabase_instance

    if not settings.is_demo:
        raise RuntimeError("Supabase client is only available in APP_ENV=demo mode")

    if _supabase_instance is None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env when APP_ENV=demo"
            )
        _supabase_instance = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key,
        )
        logger.info("supabase_client.initialized", url=settings.supabase_url)

    return _supabase_instance
