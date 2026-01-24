"""Metrics endpoint for Prometheus scraping."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from barnabeenet.services.metrics import get_metrics

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint.

    Grafana/Prometheus scrapes this endpoint to collect metrics.
    Returns metrics in Prometheus text format.
    """
    metrics_output = get_metrics()
    return Response(
        content=metrics_output,
        media_type="text/plain; charset=utf-8",
    )
