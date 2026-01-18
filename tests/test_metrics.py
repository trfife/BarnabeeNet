"""Tests for Prometheus metrics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from barnabeenet.main import app
from barnabeenet.services.metrics import (
    record_homeassistant_call,
    record_llm_request,
    record_stt_request,
    record_tts_request,
    update_component_health,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Test metrics endpoint returns Prometheus text format."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        content = response.text

        # Should contain our custom metrics
        assert "barnabeenet" in content

    def test_metrics_endpoint_includes_info(self, client):
        """Test metrics endpoint includes app info."""
        response = client.get("/metrics")
        content = response.text

        # Info metric should be present
        assert "barnabeenet_info" in content


class TestLLMMetrics:
    """Tests for LLM metrics recording."""

    def test_record_llm_request_success(self):
        """Test recording successful LLM request."""
        # This should not raise
        record_llm_request(
            agent_type="meta",
            model="deepseek/deepseek-v3",
            success=True,
            latency_seconds=0.5,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
        )

    def test_record_llm_request_failure(self):
        """Test recording failed LLM request."""
        record_llm_request(
            agent_type="interaction",
            model="claude-3-opus",
            success=False,
            latency_seconds=1.0,
            input_tokens=200,
            output_tokens=0,
            cost_usd=0.0,
        )


class TestVoiceMetrics:
    """Tests for voice pipeline metrics."""

    def test_record_stt_request(self):
        """Test recording STT request."""
        record_stt_request(
            engine="gpu",
            success=True,
            latency_seconds=0.045,
        )

        record_stt_request(
            engine="cpu",
            success=True,
            latency_seconds=2.4,
        )

    def test_record_tts_request(self):
        """Test recording TTS request."""
        record_tts_request(
            voice="bm_fable",
            success=True,
            latency_seconds=0.35,
        )


class TestHomeAssistantMetrics:
    """Tests for Home Assistant metrics."""

    def test_record_homeassistant_call(self):
        """Test recording HA service call."""
        record_homeassistant_call(
            domain="light",
            service="turn_on",
            success=True,
        )

        record_homeassistant_call(
            domain="switch",
            service="toggle",
            success=False,
        )


class TestComponentHealth:
    """Tests for component health metrics."""

    def test_update_component_health(self):
        """Test updating component health gauge."""
        update_component_health("redis", healthy=True)
        update_component_health("gpu_worker", healthy=False)
        update_component_health("orchestrator", healthy=True)
