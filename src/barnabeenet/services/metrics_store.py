"""Metrics Store - Rolling window storage for performance metrics.

Stores latency measurements for:
- STT (speech-to-text)
- TTS (text-to-speech)
- LLM (language model calls)
- Total pipeline

Supports:
- Rolling windows (last 1 hour, 24 hours)
- Aggregation (p50, p95, p99, avg)
- Time-series for graphing
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""

    timestamp: float  # Unix timestamp
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyStats:
    """Computed statistics for latency measurements."""

    component: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    sample_count: int


# =============================================================================
# Metrics Store
# =============================================================================


class MetricsStore:
    """In-memory and Redis-backed metrics storage.

    Maintains rolling windows of latency measurements for
    performance monitoring and graphing.
    """

    # Time windows in seconds
    WINDOW_1H = 3600
    WINDOW_24H = 86400

    # Components to track
    COMPONENTS = ["stt", "tts", "llm", "pipeline", "memory", "action"]

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client

        # In-memory deques for fast access (1 hour window)
        self._measurements: dict[str, deque[LatencyMeasurement]] = {
            component: deque(maxlen=10000) for component in self.COMPONENTS
        }

        # Counters
        self._total_counts: dict[str, int] = dict.fromkeys(self.COMPONENTS, 0)

    async def init(self) -> None:
        """Initialize the metrics store."""
        # Load recent measurements from Redis if available
        if self._redis:
            for component in self.COMPONENTS:
                try:
                    count = await self._redis.get(f"barnabeenet:metrics:{component}:count")
                    if count:
                        self._total_counts[component] = int(count)
                except Exception as e:
                    logger.warning("Failed to load metric count for %s: %s", component, e)

        logger.info("Metrics store initialized")

    async def shutdown(self) -> None:
        """Shutdown and persist final state."""
        if self._redis:
            for component, count in self._total_counts.items():
                try:
                    await self._redis.set(f"barnabeenet:metrics:{component}:count", count)
                except Exception as e:
                    logger.warning("Failed to persist metric count for %s: %s", component, e)

        logger.info("Metrics store shutdown")

    async def record_latency(
        self,
        component: str,
        latency_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a latency measurement.

        Args:
            component: Component name (stt, tts, llm, pipeline, etc.)
            latency_ms: Latency in milliseconds
            metadata: Optional metadata (model name, speaker, etc.)
        """
        if component not in self._measurements:
            self._measurements[component] = deque(maxlen=10000)
            self._total_counts[component] = 0

        measurement = LatencyMeasurement(
            timestamp=time.time(),
            latency_ms=latency_ms,
            metadata=metadata or {},
        )

        self._measurements[component].append(measurement)
        self._total_counts[component] += 1

        # Also persist to Redis for longer history
        if self._redis:
            try:
                await self._redis.xadd(
                    f"barnabeenet:metrics:{component}:stream",
                    {
                        "latency_ms": str(latency_ms),
                        "metadata": str(metadata or {}),
                    },
                    maxlen=50000,  # Keep 24h worth at ~2/sec
                )
            except Exception as e:
                logger.warning("Failed to persist latency to Redis: %s", e)

    async def get_latency_stats(
        self,
        component: str,
        window_seconds: int | None = None,
    ) -> LatencyStats | None:
        """Get latency statistics for a component.

        Args:
            component: Component name
            window_seconds: Time window (default: 1 hour)

        Returns:
            LatencyStats or None if no data
        """
        window_seconds = window_seconds or self.WINDOW_1H
        cutoff = time.time() - window_seconds

        if component not in self._measurements:
            return None

        # Filter by time window
        values = [m.latency_ms for m in self._measurements[component] if m.timestamp >= cutoff]

        if not values:
            return None

        # Sort for percentiles
        sorted_values = sorted(values)
        n = len(sorted_values)

        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            idx = min(idx, n - 1)
            return sorted_values[idx]

        return LatencyStats(
            component=component,
            p50_ms=percentile(50),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            avg_ms=sum(values) / n,
            min_ms=min(values),
            max_ms=max(values),
            sample_count=n,
        )

    async def get_latency_history(
        self,
        component: str,
        window_minutes: int = 60,
        bucket_seconds: int = 60,
    ) -> list[dict[str, Any]]:
        """Get latency history bucketed for graphing.

        Args:
            component: Component name
            window_minutes: How far back to look
            bucket_seconds: Bucket size for aggregation

        Returns:
            List of {timestamp, avg_ms, p95_ms, count} buckets
        """
        window_seconds = window_minutes * 60
        cutoff = time.time() - window_seconds

        if component not in self._measurements:
            return []

        # Bucket measurements
        buckets: dict[int, list[float]] = {}
        for m in self._measurements[component]:
            if m.timestamp < cutoff:
                continue
            bucket_ts = int(m.timestamp / bucket_seconds) * bucket_seconds
            if bucket_ts not in buckets:
                buckets[bucket_ts] = []
            buckets[bucket_ts].append(m.latency_ms)

        # Compute stats per bucket
        result = []
        for ts in sorted(buckets.keys()):
            values = sorted(buckets[ts])
            n = len(values)
            p95_idx = min(int(n * 0.95), n - 1)

            result.append(
                {
                    "timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
                    "unix_ts": ts,
                    "avg_ms": sum(values) / n,
                    "p95_ms": values[p95_idx],
                    "min_ms": min(values),
                    "max_ms": max(values),
                    "count": n,
                }
            )

        return result

    async def get_component_comparison(
        self,
        window_seconds: int | None = None,
    ) -> dict[str, LatencyStats | None]:
        """Get latency stats for all components for comparison."""
        window_seconds = window_seconds or self.WINDOW_1H
        return {
            component: await self.get_latency_stats(component, window_seconds)
            for component in self.COMPONENTS
        }

    def get_total_count(self, component: str) -> int:
        """Get total measurement count for a component."""
        return self._total_counts.get(component, 0)

    async def clear_component(self, component: str) -> None:
        """Clear all measurements for a component."""
        if component in self._measurements:
            self._measurements[component].clear()
            self._total_counts[component] = 0

        if self._redis:
            try:
                await self._redis.delete(f"barnabeenet:metrics:{component}:stream")
                await self._redis.delete(f"barnabeenet:metrics:{component}:count")
            except Exception as e:
                logger.warning("Failed to clear Redis metrics for %s: %s", component, e)


# =============================================================================
# Global Instance
# =============================================================================

_metrics_store: MetricsStore | None = None


async def get_metrics_store() -> MetricsStore:
    """Get or create the metrics store singleton."""
    global _metrics_store
    if _metrics_store is None:
        from barnabeenet.main import app_state

        _metrics_store = MetricsStore(redis_client=app_state.redis_client)
        await _metrics_store.init()
    return _metrics_store


async def init_metrics_store(redis_client: redis.Redis | None = None) -> MetricsStore:
    """Initialize the metrics store."""
    global _metrics_store
    _metrics_store = MetricsStore(redis_client=redis_client)
    await _metrics_store.init()
    return _metrics_store
