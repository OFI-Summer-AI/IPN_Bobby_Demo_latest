"""
Bobby — Azure Client (Production)
===================================
Lazy-loaded wrapper for Azure SDK clients.
Only initialised when APP_ENV=production.

Covers:
  - Azure Blob Storage     (document repository)
  - Azure Communication Services (email/SMS notifications)
  - Azure Key Vault        (secrets retrieval in production)

Usage:
  from integrations.azure_client import get_blob_client
  blob = get_blob_client()
"""
from __future__ import annotations
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)


def get_blob_client():
    """
    Returns an Azure Blob Storage client for the document repository.
    Only available in production mode.
    """
    if settings.is_demo:
        raise RuntimeError("Azure Blob Storage client is only available in APP_ENV=production")

    try:
        from azure.storage.blob.aio import BlobServiceClient
        connection_str = settings.azure_postgres_host  # placeholder — add AZURE_STORAGE_CONNECTION_STRING to settings
        client = BlobServiceClient.from_connection_string(connection_str)
        logger.info("azure_blob_client.initialized")
        return client
    except ImportError:
        raise ImportError(
            "azure-storage-blob package not installed. "
            "Add it to requirements.txt when enabling Azure production mode."
        )


def get_communication_client():
    """
    Returns an Azure Communication Services client for email/Teams notifications.
    Only available in production mode.
    Stub for Phase 1 — implement when ACS credentials are provisioned.
    """
    if settings.is_demo:
        raise RuntimeError("Azure Communication Services is only available in APP_ENV=production")

    try:
        from azure.communication.email.aio import EmailClient
        # TODO: Add AZURE_COMMUNICATION_CONNECTION_STRING to settings.py and .env
        logger.info("azure_communication_client.initialized")
    except ImportError:
        raise ImportError(
            "azure-communication-email package not installed. "
            "Add it to requirements.txt when enabling ACS."
        )
