"""
FastAPI application factory.

Call ``create_app()`` to get a fully configured FastAPI instance, or import
``app`` directly for use with uvicorn:

    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.exceptions import AgentOpsError
from app.core.logging import configure_logging, get_logger
from app.middleware.error_handler import (
    agent_ops_exception_handler,
    unhandled_exception_handler,
)
from app.middleware.request_logging import RequestLoggingMiddleware
from app.models.common import HealthResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "Starting %s v%s [env=%s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Registers:
    - API versioned routers
    - Exception handlers
    - CORS middleware
    - Request logging middleware

    Returns:
        FastAPI: Fully configured application instance.
    """
    configure_logging()
    settings = get_settings()

    application = FastAPI(
        title="Agent-Ops API",
        description=(
            "RESTful API for creating and managing Amazon Bedrock Agents "
            "driven by versioned YAML definition files."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "prod" else None,
        redoc_url="/redoc" if settings.APP_ENV != "prod" else None,
        lifespan=lifespan,
    )

    # ── Middleware (registered in reverse order of execution) ─────────────────
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    application.add_exception_handler(AgentOpsError, agent_ops_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Routers ───────────────────────────────────────────────────────────────
    application.include_router(v1_router, prefix="/api")

    # ── Health check ──────────────────────────────────────────────────────────
    @application.get("/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        """Liveness probe – returns 200 when the application is running."""
        return HealthResponse(
            status="ok",
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
        )

    return application


# Module-level app instance consumed by uvicorn
app = create_app()

