"""Health check API routes."""
from __future__ import annotations

import time
from datetime import datetime

import structlog
from fastapi import APIRouter

from barnabeenet import __version__
from barnabeenet.config import get_settings
from barnabeenet.models.schemas import (
    GPUWorkerStatus,
    HealthResponse,
    ServiceHealth,
)

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint.
    
    Returns overall system health and individual service status.
    """
    from barnabeenet.main import app_state

    settings = get_settings()
    services: list[ServiceHealth] = []
    overall_status = "healthy"

    # Check Redis
    redis_health = await _check_redis()
    services.append(redis_health)
    if redis_health.status != "healthy":
        overall_status = "degraded"

    # Check GPU Worker
    gpu_health = _check_gpu_worker()
    services.append(gpu_health)
    # GPU being down doesn't make us unhealthy (we have CPU fallback)

    # Check CPU STT (always available)
    services.append(
        ServiceHealth(
            name="stt_cpu",
            status="healthy",
            message="Distil-Whisper fallback available",
        )
    )

    # Check TTS
    services.append(
        ServiceHealth(
            name="tts",
            status="healthy",
            message="Kokoro TTS available",
        )
    )

    return HealthResponse(
        status=overall_status,
        version=__version__,
        timestamp=datetime.utcnow(),
        services=services,
    )


@router.get("/health/live")
async def liveness() -> dict:
    """Kubernetes liveness probe.
    
    Returns 200 if the service is running.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict:
    """Kubernetes readiness probe.
    
    Returns 200 if the service is ready to accept traffic.
    """
    from barnabeenet.main import app_state

    # Check if Redis is connected (required for working memory)
    if app_state.redis_client:
        try:
            await app_state.redis_client.ping()
            return {"status": "ready"}
        except Exception:
            pass

    # Even without Redis, we can serve requests in Phase 1
    return {"status": "ready", "warning": "Redis unavailable"}


@router.get("/health/gpu", response_model=GPUWorkerStatus)
async def gpu_worker_status() -> GPUWorkerStatus:
    """Get detailed GPU worker status."""
    from barnabeenet.main import app_state

    return GPUWorkerStatus(
        available=app_state.gpu_worker_available,
        last_check=datetime.fromtimestamp(app_state.gpu_worker_last_check)
        if app_state.gpu_worker_last_check
        else datetime.utcnow(),
        model_loaded=app_state.gpu_worker_available,  # Assume loaded if available
        error=None if app_state.gpu_worker_available else "GPU worker not responding",
    )


# =============================================================================
# Helper Functions
# =============================================================================


async def _check_redis() -> ServiceHealth:
    """Check Redis health."""
    from barnabeenet.main import app_state

    if not app_state.redis_client:
        return ServiceHealth(
            name="redis",
            status="unhealthy",
            message="Redis client not initialized",
        )

    try:
        start = time.perf_counter()
        await app_state.redis_client.ping()
        latency_ms = (time.perf_counter() - start) * 1000

        return ServiceHealth(
            name="redis",
            status="healthy",
            latency_ms=latency_ms,
        )
    except Exception as e:
        return ServiceHealth(
            name="redis",
            status="unhealthy",
            message=str(e),
        )


def _check_gpu_worker() -> ServiceHealth:
    """Check GPU worker health from cached state."""
    from barnabeenet.main import app_state

    if app_state.gpu_worker_available:
        return ServiceHealth(
            name="stt_gpu",
            status="healthy",
            message="Parakeet TDT available on Man-of-war",
        )
    else:
        return ServiceHealth(
            name="stt_gpu",
            status="degraded",
            message="GPU worker unavailable, using CPU fallback",
        )
