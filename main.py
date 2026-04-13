from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.dependencies import init_providers
from app.routers import clustering, health, hooks, similarity, websocket


def _configure_logging() -> None:
    """Configure structlog for structured JSON output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Startup:
    - Configure structlog
    - Initialise provider singletons (embedding + LLM)

    Shutdown:
    - (No-op for now — psycopg connections are per-request)
    """
    _configure_logging()
    log = structlog.get_logger()

    log.info(
        "ai_service_starting",
        embedding_provider=settings.embedding_provider,
        llm_provider=settings.llm_provider,
    )

    init_providers()

    log.info("ai_service_ready")
    yield

    log.info("ai_service_shutting_down")


app = FastAPI(
    title="DecisionMap AI Service",
    description=(
        "AI backend for DecisionMap — handles similarity detection, "
        "spam filtering, embeddings, clustering, translation, and "
        "AI-generated solution approaches."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# /similarity and /ws are called from browsers — no credentials needed (no cookies/auth headers).
# Hook endpoints are server-to-server (Directus → AI service) and protected by WEBHOOK_SECRET.
# Configure CORS_ORIGINS in .env for production (e.g. "https://app.example.com").
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Webhook-Secret"],
)

app.include_router(health.router)
app.include_router(similarity.router)
app.include_router(hooks.router)
app.include_router(clustering.router)
app.include_router(websocket.router)
