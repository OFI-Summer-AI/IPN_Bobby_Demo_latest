"""
Bobby â€” Settings (Multi-provider LLM + Dual DB Config)
========================================================
Usage:
  from config.settings import settings, LLMProvider

  # Check which LLM is active:
  settings.llm_provider          # LLMProvider.CLAUDE | .OPENAI | .AZURE_OPENAI
  settings.anthropic_api_key     # Claude API key
  settings.is_demo               # True if APP_ENV=demo

LLM_PROVIDER values:
  claude       â†’ Anthropic Claude (default)
  openai       â†’ OpenAI GPT
  azure_openai â†’ Azure OpenAI (production)
"""
from __future__ import annotations
from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    CLAUDE      = "claude"
    OPENAI      = "openai"
    AZURE_OPENAI = "azure_openai"


class AppEnv(str, Enum):
    DEMO = "demo"
    PRODUCTION = "production"


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BASE_DIR / ".env"), ".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # â”€â”€ App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    app_env: AppEnv = AppEnv.DEMO
    app_name: str = "Bobby"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # â”€â”€ LLM Provider Selection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Options: "claude" | "openai" | "azure_openai"
    # Default: claude (Anthropic) â€” change in .env to switch provider
    llm_provider: LLMProvider = LLMProvider.CLAUDE

    # â”€â”€ Claude / Anthropic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"   # latest Sonnet

    # â”€â”€ OpenAI (direct) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    openai_api_key: str = ""   # also used as embedding fallback when provider=claude
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # â”€â”€ Azure OpenAI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-large"
    azure_openai_api_version: str = "2024-02-01"

    # â”€â”€ Supabase (demo) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_db_host: str = "db.tlohofzcstxogebrhmdr.supabase.co"
    supabase_db_password: str = "ofiservices2026"
    supabase_db_user: str = "postgres"

    # â”€â”€ Azure PostgreSQL (production) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    azure_postgres_host: str = ""
    azure_postgres_db: str = "bobby"
    azure_postgres_user: str = ""
    azure_postgres_password: str = ""
    azure_postgres_port: int = 5432

    # â”€â”€ Azure AI Search (production) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index_name: str = "bobby-knowledge"

    # â”€â”€ Freshdesk â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    freshdesk_api_key: str = ""
    freshdesk_domain: str = ""  # e.g. acme.freshdesk.com

    # ── SMTP Email Service ──────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_enabled: bool = True
    smtp_user: str = ""
    smtp_username: str = ""
    smtp_to_emails: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "bobby-support@company.com"
    smtp_from_name: str = "Bobby IT Support"
    smtp_use_tls: bool = True  # e.g. acme.freshdesk.com

    # â”€â”€ Microsoft Graph API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""

    # â”€â”€ Langfuse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # â”€â”€ Derived helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    @property
    def is_demo(self) -> bool:
        return self.app_env == AppEnv.DEMO

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def database_url(self) -> str:
        """Returns the correct DB connection string based on environment."""
        if self.is_demo:
            # Supabase connection string (transaction mode, port 6543)
            return (
                f"postgresql+asyncpg://{self.supabase_url.replace('https://', '')}"
                if not self.azure_postgres_host
                else f"postgresql+asyncpg://bobby_user:bobby_local_pass@localhost:5432/bobby"
            )
        return (
            f"postgresql+asyncpg://{self.azure_postgres_user}:{self.azure_postgres_password}"
            f"@{self.azure_postgres_host}:{self.azure_postgres_port}/{self.azure_postgres_db}"
        )

    @property
    def llm_api_key(self) -> str:
        """Returns the active API key for the configured LLM provider."""
        from config.settings import LLMProvider
        if self.llm_provider == LLMProvider.CLAUDE:
            return self.anthropic_api_key
        if self.llm_provider == LLMProvider.OPENAI:
            return self.openai_api_key
        return self.azure_openai_api_key

    @property
    def llm_model(self) -> str:
        """Returns the active model name for the configured LLM provider."""
        from config.settings import LLMProvider
        if self.llm_provider == LLMProvider.CLAUDE:
            return self.anthropic_model
        if self.llm_provider == LLMProvider.OPENAI:
            return self.openai_model
        return self.azure_openai_deployment


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()



