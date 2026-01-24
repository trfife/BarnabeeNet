"""Health check endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from barnabeenet.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    """Test that health endpoint returns 200 status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
