"""BarnabeeNet - Privacy-first, multi-agent AI smart home assistant.

FastAPI application entry point.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from barnabeenet import __version__
from barnabeenet.config import get_settings
from barnabeenet.models.schemas import ErrorDetail, ErrorResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"
# =============================================================================
# Logging Setup
# =============================================================================


def setup_logging() -> None:
    """Configure structured logging."""
    settings = get_settings()

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if settings.env == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for third-party libs
    logging.basicConfig(
        level=logging.getLevelName(settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# =============================================================================
# Application State
# =============================================================================


class AppState:
    """Application state container."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.redis_client = None
        self.stt_service = None
        self.tts_service = None
        self.orchestrator = None
        self.gpu_worker_available = False
        self.gpu_worker_last_check = 0.0
        self._health_check_task: asyncio.Task | None = None
        self.pipeline_logger = None

    @property
    def uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self.start_time


app_state = AppState()


# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of services.
    """
    logger = structlog.get_logger()
    settings = get_settings()

    # --- Startup ---
    logger.info(
        "Starting BarnabeeNet",
        version=__version__,
        env=settings.env,
    )

    # Initialize Prometheus metrics
    from barnabeenet.services.metrics import init_metrics

    init_metrics(version=__version__, env=settings.env)

    # Initialize Redis connection
    try:
        import redis.asyncio as redis

        app_state.redis_client = redis.from_url(
            settings.redis.url,
            encoding="utf-8",
            decode_responses=True,
        )
        await app_state.redis_client.ping()
        # Make redis available on app.state for dependency injection
        app.state.redis = app_state.redis_client
        logger.info("Redis connected", url=settings.redis.url)

        # Load activity config overrides from Redis
        from barnabeenet.services.llm.activities import get_activity_config_manager

        manager = get_activity_config_manager()
        await manager.load_redis_overrides(app_state.redis_client)
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))
        # Continue without Redis for now - not critical for Phase 1

    # Initialize Pipeline Logger for dashboard
    try:
        from barnabeenet.services.pipeline_signals import init_pipeline_logger

        app_state.pipeline_logger = await init_pipeline_logger(redis_client=app_state.redis_client)
        logger.info("Pipeline logger initialized")
    except Exception as e:
        logger.error("Pipeline logger initialization failed", error=str(e))

    # Initialize Agent Orchestrator
    try:
        from barnabeenet.agents.orchestrator import AgentOrchestrator

        app_state.orchestrator = AgentOrchestrator(pipeline_logger=app_state.pipeline_logger)
        await app_state.orchestrator.init()
        logger.info("Agent Orchestrator initialized")
    except Exception as e:
        logger.error("Orchestrator initialization failed", error=str(e))
        # Continue - orchestrator will init lazily on first request

    # Start GPU worker health check task
    app_state._health_check_task = asyncio.create_task(_gpu_worker_health_check_loop())

    # Start model health check task (runs hourly)
    app_state._model_health_check_task = asyncio.create_task(_model_health_check_loop())

    # Start WebSocket signal streamer
    try:
        from barnabeenet.api.routes.websocket import start_signal_streamer

        await start_signal_streamer()
        logger.info("WebSocket signal streamer started")
    except Exception as e:
        logger.error("Signal streamer startup failed", error=str(e))

    logger.info(
        "BarnabeeNet started",
        host=settings.host,
        port=settings.port,
    )

    yield

    # --- Shutdown ---
    logger.info("Shutting down BarnabeeNet")

    # Stop WebSocket signal streamer
    try:
        from barnabeenet.api.routes.websocket import stop_signal_streamer

        await stop_signal_streamer()
    except Exception as e:
        logger.warning("Signal streamer shutdown error", error=str(e))

    # Shutdown orchestrator
    if app_state.orchestrator:
        await app_state.orchestrator.shutdown()

    # Cancel health check task
    if app_state._health_check_task:
        app_state._health_check_task.cancel()
        try:
            await app_state._health_check_task
        except asyncio.CancelledError:
            pass

    # Cancel model health check task
    if hasattr(app_state, "_model_health_check_task") and app_state._model_health_check_task:
        app_state._model_health_check_task.cancel()
        try:
            await app_state._model_health_check_task
        except asyncio.CancelledError:
            pass

    # Close Redis connection
    if app_state.redis_client:
        await app_state.redis_client.close()

    logger.info("BarnabeeNet stopped")


async def _gpu_worker_health_check_loop() -> None:
    """Background task to check GPU worker availability."""
    logger = structlog.get_logger()
    settings = get_settings()

    while True:
        try:
            await _check_gpu_worker()
        except Exception as e:
            logger.warning("GPU health check error", error=str(e))
            app_state.gpu_worker_available = False

        await asyncio.sleep(settings.stt.gpu_worker_health_interval_sec)


async def _check_gpu_worker() -> None:
    """Check if GPU worker is available."""
    import httpx

    settings = get_settings()
    url = f"http://{settings.stt.gpu_worker_host}:{settings.stt.gpu_worker_port}/health"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                timeout=settings.stt.gpu_worker_timeout_ms / 1000,
            )
            app_state.gpu_worker_available = response.status_code == 200
            app_state.gpu_worker_last_check = time.time()
    except Exception:
        app_state.gpu_worker_available = False
        app_state.gpu_worker_last_check = time.time()


async def _model_health_check_loop() -> None:
    """Background task to check LLM model health every hour."""
    logger = structlog.get_logger()

    # Wait 30 seconds before first check to let app fully start
    await asyncio.sleep(30)

    while True:
        try:
            from barnabeenet.api.routes.config import run_scheduled_health_check
            from barnabeenet.services.secrets import SecretsService

            secrets = SecretsService()
            await secrets.initialize()

            result = await run_scheduled_health_check(secrets, limit=20)
            if result:
                logger.info(
                    "Scheduled model health check complete",
                    working=result.working,
                    failed=result.failed,
                    total=result.checked,
                )
        except Exception as e:
            logger.warning("Model health check error", error=str(e))

        # Sleep for 1 hour
        await asyncio.sleep(3600)


# =============================================================================
# FastAPI Application
# =============================================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title="BarnabeeNet",
        description="Privacy-first, multi-agent AI smart home assistant",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.env == "development" else None,
        redoc_url="/redoc" if settings.env == "development" else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request timing middleware
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger = structlog.get_logger()
        logger.error(
            "Unhandled exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                    details={"error": str(exc)} if settings.debug else None,
                )
            ).model_dump(mode="json"),
        )

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routes."""
    from barnabeenet.api.routes import (
        activity,
        config,
        dashboard,
        e2e,
        health,
        homeassistant,
        metrics,
        prompts,
        voice,
        websocket,
    )

    # Root endpoint - serve dashboard
    @app.get("/", include_in_schema=False)
    async def root():
        """Serve the dashboard."""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        # Fallback to API info if no dashboard
        return {
            "name": "BarnabeeNet",
            "version": __version__,
            "description": "Privacy-first, multi-agent AI smart home assistant",
            "endpoints": {
                "health": "/health",
                "docs": "/docs",
                "api": "/api/v1",
                "metrics": "/metrics",
                "dashboard_status": "/api/v1/dashboard/status",
                "websocket": "/api/v1/ws/activity",
                "e2e_tests": "/api/v1/e2e/tests",
                "config": "/api/v1/config/providers",
            },
        }

    # API routes
    app.include_router(health.router, tags=["Health"])
    app.include_router(voice.router, prefix="/api/v1", tags=["Voice"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
    app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
    app.include_router(activity.router, prefix="/api/v1", tags=["Activity"])
    app.include_router(e2e.router, prefix="/api/v1", tags=["E2E Testing"])
    app.include_router(homeassistant.router, prefix="/api/v1", tags=["Home Assistant"])
    app.include_router(prompts.router, prefix="/api/v1", tags=["Prompts"])
    app.include_router(metrics.router, tags=["Metrics"])
    app.include_router(websocket.router, prefix="/api/v1", tags=["WebSocket"])

    # Mount static files (must be after routes to not override them)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Create app instance
app = create_app()


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> None:
    """Run the application via CLI."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "barnabeenet.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.env == "development",
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
