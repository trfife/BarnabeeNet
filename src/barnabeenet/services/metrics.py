"""Prometheus metrics for BarnabeeNet.

Exposes metrics for Grafana dashboards:
- Request counts and latencies
- LLM usage and costs
- Service health
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest
from prometheus_client.core import CollectorRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# =============================================================================
# Custom Registry (avoids conflicts in tests)
# =============================================================================

REGISTRY = CollectorRegistry(auto_describe=True)

# =============================================================================
# Application Metrics
# =============================================================================

# System info
barnabeenet_info = Info(
    "barnabeenet",
    "BarnabeeNet version and environment info",
    registry=REGISTRY,
)

# Uptime
barnabeenet_uptime = Gauge(
    "barnabeenet_uptime_seconds",
    "Time since BarnabeeNet started",
    registry=REGISTRY,
)

# =============================================================================
# HTTP Request Metrics
# =============================================================================

http_requests_total = Counter(
    "barnabeenet_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "barnabeenet_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

# =============================================================================
# LLM Metrics
# =============================================================================

llm_requests_total = Counter(
    "barnabeenet_llm_requests_total",
    "Total LLM API requests",
    ["agent_type", "model", "status"],
    registry=REGISTRY,
)

llm_request_duration_seconds = Histogram(
    "barnabeenet_llm_request_duration_seconds",
    "LLM request latency",
    ["agent_type", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=REGISTRY,
)

llm_tokens_total = Counter(
    "barnabeenet_llm_tokens_total",
    "Total tokens used",
    ["agent_type", "model", "direction"],  # direction: input/output
    registry=REGISTRY,
)

llm_cost_usd_total = Counter(
    "barnabeenet_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["agent_type", "model"],
    registry=REGISTRY,
)

# =============================================================================
# Voice Pipeline Metrics
# =============================================================================

stt_requests_total = Counter(
    "barnabeenet_stt_requests_total",
    "Total STT requests",
    ["engine", "status"],  # engine: gpu/cpu
    registry=REGISTRY,
)

stt_duration_seconds = Histogram(
    "barnabeenet_stt_duration_seconds",
    "STT processing time",
    ["engine"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY,
)

tts_requests_total = Counter(
    "barnabeenet_tts_requests_total",
    "Total TTS requests",
    ["voice", "status"],
    registry=REGISTRY,
)

tts_duration_seconds = Histogram(
    "barnabeenet_tts_duration_seconds",
    "TTS processing time",
    ["voice"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=REGISTRY,
)

# =============================================================================
# Agent Metrics
# =============================================================================

agent_requests_total = Counter(
    "barnabeenet_agent_requests_total",
    "Total agent requests",
    ["agent_type", "status"],
    registry=REGISTRY,
)

agent_routing_total = Counter(
    "barnabeenet_agent_routing_total",
    "Agent routing decisions",
    ["selected_agent"],
    registry=REGISTRY,
)

# =============================================================================
# Memory Metrics
# =============================================================================

memory_operations_total = Counter(
    "barnabeenet_memory_operations_total",
    "Total memory operations",
    ["operation"],  # store/retrieve/search
    registry=REGISTRY,
)

memory_stored_total = Gauge(
    "barnabeenet_memory_stored_total",
    "Total memories stored",
    registry=REGISTRY,
)

# =============================================================================
# Home Assistant Metrics
# =============================================================================

homeassistant_calls_total = Counter(
    "barnabeenet_homeassistant_calls_total",
    "Total Home Assistant service calls",
    ["domain", "service", "status"],
    registry=REGISTRY,
)

homeassistant_entities_total = Gauge(
    "barnabeenet_homeassistant_entities_total",
    "Total entities in Home Assistant registry",
    ["domain"],
    registry=REGISTRY,
)

# =============================================================================
# Component Health Gauges
# =============================================================================

component_healthy = Gauge(
    "barnabeenet_component_healthy",
    "Component health status (1=healthy, 0=unhealthy)",
    ["component"],
    registry=REGISTRY,
)


# =============================================================================
# Helper Functions
# =============================================================================


def record_llm_request(
    agent_type: str,
    model: str,
    success: bool,
    latency_seconds: float,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """Record metrics for an LLM request."""
    status = "success" if success else "error"

    llm_requests_total.labels(agent_type=agent_type, model=model, status=status).inc()
    llm_request_duration_seconds.labels(agent_type=agent_type, model=model).observe(latency_seconds)
    llm_tokens_total.labels(agent_type=agent_type, model=model, direction="input").inc(input_tokens)
    llm_tokens_total.labels(agent_type=agent_type, model=model, direction="output").inc(
        output_tokens
    )
    llm_cost_usd_total.labels(agent_type=agent_type, model=model).inc(cost_usd)


def record_stt_request(engine: str, success: bool, latency_seconds: float) -> None:
    """Record metrics for an STT request."""
    status = "success" if success else "error"
    stt_requests_total.labels(engine=engine, status=status).inc()
    stt_duration_seconds.labels(engine=engine).observe(latency_seconds)


def record_tts_request(voice: str, success: bool, latency_seconds: float) -> None:
    """Record metrics for a TTS request."""
    status = "success" if success else "error"
    tts_requests_total.labels(voice=voice, status=status).inc()
    tts_duration_seconds.labels(voice=voice).observe(latency_seconds)


def record_homeassistant_call(domain: str, service: str, success: bool) -> None:
    """Record metrics for a Home Assistant service call."""
    status = "success" if success else "error"
    homeassistant_calls_total.labels(domain=domain, service=service, status=status).inc()


def update_component_health(component: str, healthy: bool) -> None:
    """Update component health gauge."""
    component_healthy.labels(component=component).set(1 if healthy else 0)


@asynccontextmanager
async def track_http_request(method: str, endpoint: str) -> AsyncGenerator[None, None]:
    """Context manager to track HTTP request metrics."""
    start = time.perf_counter()
    status = "500"
    try:
        yield
        status = "200"
    except Exception:
        status = "500"
        raise
    finally:
        duration = time.perf_counter() - start
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest(REGISTRY)


def init_metrics(version: str, env: str) -> None:
    """Initialize static metrics."""
    barnabeenet_info.info({"version": version, "environment": env})
