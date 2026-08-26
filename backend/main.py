"""
Bobby - FastAPI Main Application
==================================
Entry point for the Bobby backend API.
Registers all routers, persistent checkpointer startup, and lifespan handlers.
"""
from __future__ import annotations
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import os
from config.settings import settings
if settings.langfuse_public_key:
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host or "https://cloud.langfuse.com"
    os.environ["LANGFUSE_BASE_URL"] = settings.langfuse_host or "https://cloud.langfuse.com"

from api.commands import ticket_commands, account_commands
from api.queries import ticket_queries, knowledge_queries
from api.routes import health, auth
from agent.graph import init_persistent_checkpointer, close_persistent_checkpointer

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info(
        "bobby.startup",
        env=settings.app_env.value,
        freshdesk_domain=settings.freshdesk_domain or "NOT SET",
    )
    # Initialize persistent checkpointer in Supabase
    await init_persistent_checkpointer()
    logger.info("bobby.graph_ready")
    yield
    await close_persistent_checkpointer()
    logger.info("bobby.shutdown")


app = FastAPI(
    title="Bobby - AI Service Management API",
    description="Bobby's backend API. Commands go through LangGraph with Supabase persistence. Queries go direct.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CQRS Commands
app.include_router(ticket_commands.router,  tags=["Commands"])
app.include_router(account_commands.router, tags=["Commands"])

# CQRS Queries
app.include_router(ticket_queries.router,    tags=["Queries"])
app.include_router(knowledge_queries.router, tags=["Queries"])

# Health
app.include_router(health.router, tags=["Health"])

# Auth
app.include_router(auth.router, tags=["Auth"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Bobby AI",
        "env": settings.app_env.value,
        "status": "running",
        "docs": "/docs",
    }
