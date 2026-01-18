"""Dashboard Service Layer - Central hub for all dashboard data.

Aggregates data from multiple sources:
- Real-time metrics (STT/TTS/LLM latencies)
- System health monitoring
- Test execution interface
- Activity feed management
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import redis.asyncio as redis

    from barnabeenet.services.metrics_store import MetricsStore

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class ServiceStatus(BaseModel):
    """Status of a single service."""

    name: str
    status: str  # healthy, degraded, unhealthy, unknown
    latency_ms: float | None = None
    last_check: datetime | None = None
    message: str | None = None


class SystemHealth(BaseModel):
    """Overall system health summary."""

    status: str  # healthy, degraded, unhealthy
    services: list[ServiceStatus]
    uptime_seconds: float
    memory_mb: float | None = None
    cpu_percent: float | None = None
    active_connections: int = 0


class LatencyMetrics(BaseModel):
    """Latency statistics for a component."""

    component: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    sample_count: int


class DashboardStats(BaseModel):
    """Dashboard statistics summary."""

    total_requests: int = 0
    total_signals: int = 0
    total_memories: int = 0
    total_actions: int = 0
    errors_last_hour: int = 0
    avg_pipeline_latency_ms: float | None = None

    # Component breakdowns (LatencyStats from metrics_store)
    stt_latency: dict[str, Any] | None = None
    tts_latency: dict[str, Any] | None = None
    llm_latency: dict[str, Any] | None = None


class ActivityItem(BaseModel):
    """Single activity feed item."""

    id: str
    timestamp: datetime
    type: str
    level: str = "info"  # debug, info, warn, error
    component: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    source: str = "system"  # system, ha, llm, voice, etc.


class TestResult(BaseModel):
    """Result of a single test."""

    name: str
    status: str  # passed, failed, skipped, error
    duration_ms: float
    message: str | None = None
    assertions: list[dict[str, Any]] = Field(default_factory=list)


class TestRunResult(BaseModel):
    """Result of a test run."""

    run_id: str
    category: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"  # running, passed, failed, error
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    tests: list[TestResult] = Field(default_factory=list)


# =============================================================================
# Dashboard Service
# =============================================================================


class DashboardService:
    """Central service for dashboard data aggregation.

    Provides:
    - Real-time metrics collection
    - System health monitoring
    - Test execution interface
    - Activity feed management
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client
        self._metrics_store: MetricsStore | None = None
        self._active_test_runs: dict[str, TestRunResult] = {}
        self._recent_activities: list[ActivityItem] = []
        self._max_activities = 1000

    async def init(self) -> None:
        """Initialize the dashboard service."""
        from barnabeenet.services.metrics_store import MetricsStore

        self._metrics_store = MetricsStore(redis_client=self._redis)
        await self._metrics_store.init()
        logger.info("Dashboard service initialized")

    async def shutdown(self) -> None:
        """Shutdown the dashboard service."""
        if self._metrics_store:
            await self._metrics_store.shutdown()
        logger.info("Dashboard service shutdown")

    # -------------------------------------------------------------------------
    # System Health
    # -------------------------------------------------------------------------

    async def get_system_health(self) -> SystemHealth:
        """Get overall system health status."""
        import psutil

        from barnabeenet.main import app_state

        services = []

        # Check Redis
        redis_status = ServiceStatus(
            name="redis",
            status="unknown",
            message="Not initialized",
        )
        if self._redis:
            try:
                start = datetime.now(UTC)
                await self._redis.ping()
                latency = (datetime.now(UTC) - start).total_seconds() * 1000
                redis_status = ServiceStatus(
                    name="redis",
                    status="healthy",
                    latency_ms=latency,
                    last_check=datetime.now(UTC),
                )
            except Exception as e:
                redis_status = ServiceStatus(
                    name="redis",
                    status="unhealthy",
                    message=str(e),
                    last_check=datetime.now(UTC),
                )
        services.append(redis_status)

        # Check GPU Worker
        gpu_status = ServiceStatus(
            name="gpu_worker",
            status="healthy" if app_state.gpu_worker_available else "unavailable",
            message="GPU STT acceleration"
            if app_state.gpu_worker_available
            else "Using CPU fallback",
            last_check=datetime.fromtimestamp(app_state.gpu_worker_last_check, tz=UTC)
            if app_state.gpu_worker_last_check
            else None,
        )
        services.append(gpu_status)

        # Check Orchestrator
        orch_status = ServiceStatus(
            name="orchestrator",
            status="healthy" if app_state.orchestrator else "degraded",
            message="Agent routing active" if app_state.orchestrator else "Not initialized",
        )
        services.append(orch_status)

        # Overall status
        unhealthy_count = sum(1 for s in services if s.status == "unhealthy")
        degraded_count = sum(1 for s in services if s.status in ("degraded", "unavailable"))

        if unhealthy_count > 0:
            overall = "unhealthy"
        elif degraded_count > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        # Get WebSocket connection count
        try:
            from barnabeenet.api.routes.websocket import manager

            active_connections = manager.connection_count
        except Exception:
            active_connections = 0

        return SystemHealth(
            status=overall,
            services=services,
            uptime_seconds=app_state.uptime_seconds,
            memory_mb=psutil.Process().memory_info().rss / 1024 / 1024,
            cpu_percent=psutil.cpu_percent(),
            active_connections=active_connections,
        )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    async def get_stats(self) -> DashboardStats:
        """Get dashboard statistics."""
        stats = DashboardStats()

        if self._redis:
            try:
                # Get request count
                stats.total_requests = int(await self._redis.get("barnabeenet:stats:requests") or 0)
                stats.total_signals = int(await self._redis.get("barnabeenet:stats:signals") or 0)
                stats.total_memories = int(await self._redis.get("barnabeenet:stats:memories") or 0)
                stats.total_actions = int(await self._redis.get("barnabeenet:stats:actions") or 0)
                stats.errors_last_hour = int(
                    await self._redis.get("barnabeenet:stats:errors_hour") or 0
                )
            except Exception as e:
                logger.warning("Failed to get stats from Redis: %s", e)

        # Get latency metrics from metrics store
        if self._metrics_store:
            stt_stats = await self._metrics_store.get_latency_stats("stt")
            tts_stats = await self._metrics_store.get_latency_stats("tts")
            llm_stats = await self._metrics_store.get_latency_stats("llm")

            # Convert to dicts for JSON serialization
            if stt_stats:
                stats.stt_latency = {
                    "component": stt_stats.component,
                    "p50_ms": stt_stats.p50_ms,
                    "p95_ms": stt_stats.p95_ms,
                    "p99_ms": stt_stats.p99_ms,
                    "avg_ms": stt_stats.avg_ms,
                    "min_ms": stt_stats.min_ms,
                    "max_ms": stt_stats.max_ms,
                    "sample_count": stt_stats.sample_count,
                }
            if tts_stats:
                stats.tts_latency = {
                    "component": tts_stats.component,
                    "p50_ms": tts_stats.p50_ms,
                    "p95_ms": tts_stats.p95_ms,
                    "p99_ms": tts_stats.p99_ms,
                    "avg_ms": tts_stats.avg_ms,
                    "min_ms": tts_stats.min_ms,
                    "max_ms": tts_stats.max_ms,
                    "sample_count": tts_stats.sample_count,
                }
            if llm_stats:
                stats.llm_latency = {
                    "component": llm_stats.component,
                    "p50_ms": llm_stats.p50_ms,
                    "p95_ms": llm_stats.p95_ms,
                    "p99_ms": llm_stats.p99_ms,
                    "avg_ms": llm_stats.avg_ms,
                    "min_ms": llm_stats.min_ms,
                    "max_ms": llm_stats.max_ms,
                    "sample_count": llm_stats.sample_count,
                }

            if stt_stats and tts_stats and llm_stats:
                stats.avg_pipeline_latency_ms = (
                    stt_stats.avg_ms + tts_stats.avg_ms + llm_stats.avg_ms
                )

        return stats

    # -------------------------------------------------------------------------
    # Metrics Recording
    # -------------------------------------------------------------------------

    async def record_latency(
        self,
        component: str,
        latency_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a latency measurement."""
        if self._metrics_store:
            await self._metrics_store.record_latency(component, latency_ms, metadata)

    async def get_latency_history(
        self,
        component: str,
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Get latency history for graphing."""
        if self._metrics_store:
            return await self._metrics_store.get_latency_history(component, window_minutes)
        return []

    # -------------------------------------------------------------------------
    # Activity Feed
    # -------------------------------------------------------------------------

    async def add_activity(self, activity: ActivityItem) -> None:
        """Add an activity to the feed."""
        self._recent_activities.insert(0, activity)

        # Trim to max size
        if len(self._recent_activities) > self._max_activities:
            self._recent_activities = self._recent_activities[: self._max_activities]

        # Also persist to Redis for longer history
        if self._redis:
            try:
                await self._redis.xadd(
                    "barnabeenet:activity:stream",
                    {
                        "data": activity.model_dump_json(),
                    },
                    maxlen=5000,
                )
            except Exception as e:
                logger.warning("Failed to persist activity: %s", e)

    async def get_recent_activities(
        self,
        limit: int = 100,
        component: str | None = None,
        level: str | None = None,
        source: str | None = None,
    ) -> list[ActivityItem]:
        """Get recent activities with optional filtering."""
        activities = self._recent_activities

        if component:
            activities = [a for a in activities if a.component == component]
        if level:
            activities = [a for a in activities if a.level == level]
        if source:
            activities = [a for a in activities if a.source == source]

        return activities[:limit]

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------

    async def start_test_run(
        self,
        run_id: str,
        category: str,
    ) -> TestRunResult:
        """Start a new test run."""
        result = TestRunResult(
            run_id=run_id,
            category=category,
            started_at=datetime.now(UTC),
        )
        self._active_test_runs[run_id] = result
        return result

    async def add_test_result(
        self,
        run_id: str,
        test: TestResult,
    ) -> None:
        """Add a test result to an active run."""
        if run_id not in self._active_test_runs:
            return

        run = self._active_test_runs[run_id]
        run.tests.append(test)
        run.total += 1

        if test.status == "passed":
            run.passed += 1
        elif test.status == "failed":
            run.failed += 1
        elif test.status == "skipped":
            run.skipped += 1

    async def complete_test_run(self, run_id: str) -> TestRunResult | None:
        """Complete a test run."""
        if run_id not in self._active_test_runs:
            return None

        run = self._active_test_runs[run_id]
        run.completed_at = datetime.now(UTC)
        run.status = "passed" if run.failed == 0 else "failed"

        # Remove from active runs (but could persist to history)
        del self._active_test_runs[run_id]

        return run

    async def get_test_run(self, run_id: str) -> TestRunResult | None:
        """Get a test run by ID."""
        return self._active_test_runs.get(run_id)


# =============================================================================
# Global Instance
# =============================================================================

_dashboard_service: DashboardService | None = None


async def get_dashboard_service() -> DashboardService:
    """Get or create the dashboard service singleton."""
    global _dashboard_service
    if _dashboard_service is None:
        from barnabeenet.main import app_state

        _dashboard_service = DashboardService(redis_client=app_state.redis_client)
        await _dashboard_service.init()
    return _dashboard_service


async def init_dashboard_service(redis_client: redis.Redis | None = None) -> DashboardService:
    """Initialize the dashboard service."""
    global _dashboard_service
    _dashboard_service = DashboardService(redis_client=redis_client)
    await _dashboard_service.init()
    return _dashboard_service
