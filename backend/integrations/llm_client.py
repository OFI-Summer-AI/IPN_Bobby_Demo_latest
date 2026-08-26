"""
Bobby — LLM Client (Multi-Provider Abstraction)
=================================================
Supports three providers, selected via LLM_PROVIDER in .env:

  LLM_PROVIDER=claude        → Anthropic Claude (current default)
  LLM_PROVIDER=openai        → OpenAI GPT
  LLM_PROVIDER=azure_openai  → Azure OpenAI (production)

All nodes and tools call get_llm() — no changes needed there
when switching provider. Only .env needs updating.

Embeddings:
  Claude does not provide embeddings. When LLM_PROVIDER=claude,
  embeddings fall back to OpenAI (if key set) or a stub.
  For production, Azure OpenAI embeddings are always used.
"""
from __future__ import annotations
import structlog
from config.settings import settings, LLMProvider

logger = structlog.get_logger(__name__)


def get_llm(json_mode: bool = False):
    """
    Returns a LangChain ChatModel for the configured LLM_PROVIDER.

    Args:
        json_mode : If True, forces structured JSON output.
                    Note: Claude uses a different mechanism than OpenAI
                    for JSON mode — handled transparently here.

    Returns:
        LangChain BaseChatModel — same interface regardless of provider.
    """
    provider = settings.llm_provider
    logger.debug("get_llm.provider", provider=provider.value)

    # ── Claude (Anthropic) ────────────────────────────────────────────────────
    if provider == LLMProvider.CLAUDE:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic not installed. "
                "Run: pip install langchain-anthropic"
            )
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=claude")

        kwargs: dict = {}
        if json_mode:
            # Claude uses tool_choice / system prompt for JSON — add a system hint
            # The triage/slot-fill nodes already request JSON in their system prompts
            pass  # No extra kwargs needed; Claude respects "Return ONLY valid JSON" in prompt

        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            temperature=0,
            max_tokens=4096,
            streaming=True,
        )

    # ── OpenAI ────────────────────────────────────────────────────────────────
    if provider == LLMProvider.OPENAI:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("langchain-openai not installed. Run: pip install langchain-openai")

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER=openai")

        kwargs = {}
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0,
            streaming=True,
            **kwargs,
        )

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    if provider == LLMProvider.AZURE_OPENAI:
        try:
            from langchain_openai import AzureChatOpenAI
        except ImportError:
            raise ImportError("langchain-openai not installed. Run: pip install langchain-openai")

        if not settings.azure_openai_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY must be set when LLM_PROVIDER=azure_openai")

        kwargs = {}
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

        return AzureChatOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            temperature=0,
            streaming=True,
            **kwargs,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Must be claude | openai | azure_openai")


def get_embedding_model():
    """
    Returns a LangChain embedding model.

    Provider priority:
      1. Azure OpenAI embeddings  (if LLM_PROVIDER=azure_openai)
      2. OpenAI embeddings        (if OPENAI_API_KEY is set)
      3. Claude has no embeddings — falls back to OpenAI key if provided,
         otherwise raises with a clear message.
    """
    provider = settings.llm_provider

    if provider == LLMProvider.AZURE_OPENAI:
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_deployment=settings.azure_openai_embedding_deployment,
            api_version=settings.azure_openai_api_version,
        )

    # OpenAI or Claude (Claude fallback to OpenAI for embeddings)
    if settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings
        logger.debug(
            "get_embedding_model.using_openai",
            note="Claude does not provide embeddings — using OpenAI for embeddings"
            if provider == LLMProvider.CLAUDE else "",
        )
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )

    raise ValueError(
        "No embedding model available. "
        "When LLM_PROVIDER=claude, set OPENAI_API_KEY for embeddings, "
        "or switch to LLM_PROVIDER=azure_openai."
    )
