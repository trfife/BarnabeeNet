"""E2E Testing API routes.

Endpoints for running and monitoring end-to-end voice pipeline tests.
Test results are logged to the dashboard for visibility.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from barnabeenet.services.e2e_tester import (
    TestCategory,
    TestSuiteConfig,
    get_test_runner,
)
from barnabeenet.services.homeassistant.mock_ha import (
    disable_mock_ha,
    enable_mock_ha,
    get_mock_ha,
    reset_mock_ha,
)

router = APIRouter(prefix="/e2e", tags=["E2E Testing"])


# =============================================================================
# Request/Response Models
# =============================================================================


class RunSuiteRequest(BaseModel):
    """Request to run a test suite."""

    suite_name: str = Field(default="manual", description="Name for this test run")
    categories: list[str] | None = Field(
        default=None, description="Test categories to include (instant, action, interaction)"
    )
    include_llm_tests: bool = Field(default=False, description="Include tests requiring LLM calls")
    delay_between_tests_ms: int = Field(
        default=100, ge=0, le=5000, description="Delay between tests"
    )


class TestSuiteResponse(BaseModel):
    """Response from test suite execution."""

    suite_id: str
    suite_name: str
    started_at: str
    completed_at: str | None
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    success_rate: float
    total_latency_ms: float
    test_results: list[dict[str, Any]]


class AvailableTestsResponse(BaseModel):
    """Response listing available tests."""

    total: int
    categories: list[str]
    tests: list[dict[str, Any]]


class SingleTestResponse(BaseModel):
    """Response from running a single test."""

    id: str
    name: str
    result: str
    response_text: str
    agent_used: str
    intent: str
    latency_ms: float
    assertions: list[dict[str, Any]]
    error: str | None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/tests", response_model=AvailableTestsResponse)
async def list_available_tests() -> AvailableTestsResponse:
    """List all available E2E tests.

    Returns test definitions grouped by category.
    """
    runner = get_test_runner()
    tests = runner.get_available_tests()

    categories = list({t["category"] for t in tests})

    return AvailableTestsResponse(
        total=len(tests),
        categories=sorted(categories),
        tests=tests,
    )


@router.post("/run", response_model=TestSuiteResponse)
async def run_test_suite(request: RunSuiteRequest | None = None) -> TestSuiteResponse:
    """Run a test suite.

    Executes tests based on configuration and logs all results to the dashboard.
    Test signals appear in the activity feed and trace list.

    Example: Run only instant tests (fast, no LLM):
    ```json
    {"suite_name": "instant_check", "categories": ["instant"]}
    ```

    Example: Run all tests including LLM:
    ```json
    {"suite_name": "full_suite", "include_llm_tests": true}
    ```
    """
    if request is None:
        request = RunSuiteRequest()

    # Convert category strings to enums
    categories = None
    if request.categories:
        try:
            categories = [TestCategory(c) for c in request.categories]
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {e}. Valid: instant, action, interaction",
            ) from e

    config = TestSuiteConfig(
        suite_name=request.suite_name,
        categories=categories,
        include_llm_tests=request.include_llm_tests,
        delay_between_tests_ms=request.delay_between_tests_ms,
    )

    runner = get_test_runner()
    result = await runner.run_suite(config)

    success_rate = (result.passed / result.total_tests * 100) if result.total_tests > 0 else 0

    return TestSuiteResponse(
        suite_id=result.suite_id,
        suite_name=result.suite_name,
        started_at=result.started_at.isoformat(),
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        total_tests=result.total_tests,
        passed=result.passed,
        failed=result.failed,
        errors=result.errors,
        skipped=result.skipped,
        success_rate=round(success_rate, 1),
        total_latency_ms=round(result.total_latency_ms, 2),
        test_results=result.test_results,
    )


@router.post("/run/{test_id}", response_model=SingleTestResponse)
async def run_single_test(test_id: str) -> SingleTestResponse:
    """Run a single test by ID.

    Useful for debugging specific test cases. Results appear in dashboard.
    """
    runner = get_test_runner()
    result = await runner.run_single_test(test_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found")

    return SingleTestResponse(
        id=result.id,
        name=result.name,
        result=result.result.value,
        response_text=result.response_text[:200] if result.response_text else "",
        agent_used=result.agent_used,
        intent=result.intent,
        latency_ms=round(result.latency_ms, 2),
        assertions=[
            {
                "type": a.type.value,
                "expected": str(a.expected),
                "actual": str(a.actual),
                "passed": a.passed,
                "message": a.message,
            }
            for a in result.assertions
        ],
        error=result.error,
    )


@router.get("/categories")
async def list_categories() -> dict[str, Any]:
    """List test categories with descriptions."""
    return {
        "categories": [
            {
                "id": "instant",
                "name": "Instant Agent Tests",
                "description": "Time, date, greetings, math - fast responses, no LLM",
            },
            {
                "id": "action",
                "name": "Action Agent Tests",
                "description": "Device control commands - tests intent parsing",
            },
            {
                "id": "interaction",
                "name": "Interaction Agent Tests",
                "description": "Complex conversations - requires LLM, slower",
            },
            {
                "id": "memory",
                "name": "Memory Agent Tests",
                "description": "Memory storage and retrieval - tests context",
            },
            {
                "id": "pipeline",
                "name": "Pipeline Tests",
                "description": "Full flow tests including STT/TTS",
            },
        ]
    }


@router.post("/quick")
async def quick_test() -> TestSuiteResponse:
    """Run a quick test suite (instant tests only).

    Fast sanity check that doesn't require LLM calls.
    Typically completes in under 3 seconds.
    """
    config = TestSuiteConfig(
        suite_name="quick_check",
        categories=[TestCategory.INSTANT],
        include_llm_tests=False,
        delay_between_tests_ms=50,
    )

    runner = get_test_runner()
    result = await runner.run_suite(config)

    success_rate = (result.passed / result.total_tests * 100) if result.total_tests > 0 else 0

    return TestSuiteResponse(
        suite_id=result.suite_id,
        suite_name=result.suite_name,
        started_at=result.started_at.isoformat(),
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        total_tests=result.total_tests,
        passed=result.passed,
        failed=result.failed,
        errors=result.errors,
        skipped=result.skipped,
        success_rate=round(success_rate, 1),
        total_latency_ms=round(result.total_latency_ms, 2),
        test_results=result.test_results,
    )


# =============================================================================
# Mock Home Assistant Endpoints
# =============================================================================


class MockHAStatusResponse(BaseModel):
    """Status of the mock Home Assistant."""

    enabled: bool
    entity_count: int
    area_count: int
    service_call_count: int


class MockHAEntitiesResponse(BaseModel):
    """List of mock HA entities."""

    entities: list[dict[str, Any]]
    total: int


class MockHAServiceHistoryResponse(BaseModel):
    """History of mock HA service calls."""

    calls: list[dict[str, Any]]
    total: int


@router.get("/mock-ha/status", response_model=MockHAStatusResponse)
async def get_mock_ha_status() -> MockHAStatusResponse:
    """Get status of the mock Home Assistant.

    Shows whether mock mode is enabled and counts of entities/areas/calls.
    """
    mock_ha = get_mock_ha()
    return MockHAStatusResponse(
        enabled=mock_ha.is_enabled,
        entity_count=len(mock_ha.get_entities()),
        area_count=len(mock_ha.get_areas()),
        service_call_count=len(mock_ha.get_service_call_history()),
    )


@router.post("/mock-ha/enable")
async def enable_mock_ha_mode() -> dict[str, Any]:
    """Enable mock Home Assistant mode.

    When enabled, action tests will use the mock HA instead of a real instance.
    Mock HA has predefined entities in common rooms (living room, kitchen, etc.).
    """
    enable_mock_ha()
    mock_ha = get_mock_ha()
    return {
        "status": "enabled",
        "message": "Mock Home Assistant enabled for testing",
        "entity_count": len(mock_ha.get_entities()),
        "area_count": len(mock_ha.get_areas()),
    }


@router.post("/mock-ha/disable")
async def disable_mock_ha_mode() -> dict[str, Any]:
    """Disable mock Home Assistant mode.

    Reverts to using the real HA instance (if configured).
    """
    disable_mock_ha()
    return {
        "status": "disabled",
        "message": "Mock Home Assistant disabled",
    }


@router.post("/mock-ha/reset")
async def reset_mock_ha_state() -> dict[str, Any]:
    """Reset mock HA to default state.

    Restores all entities to their initial states and clears service history.
    """
    reset_mock_ha()
    mock_ha = get_mock_ha()
    return {
        "status": "reset",
        "message": "Mock Home Assistant reset to defaults",
        "entity_count": len(mock_ha.get_entities()),
    }


@router.get("/mock-ha/entities", response_model=MockHAEntitiesResponse)
async def get_mock_ha_entities(domain: str | None = None) -> MockHAEntitiesResponse:
    """Get mock HA entities.

    Args:
        domain: Filter by domain (e.g., 'light', 'switch', 'cover')
    """
    mock_ha = get_mock_ha()
    entities = mock_ha.get_entities(domain)

    return MockHAEntitiesResponse(
        entities=[
            {
                "entity_id": e.entity_id,
                "domain": e.domain,
                "friendly_name": e.friendly_name,
                "area_id": e.area_id,
                "state": e.state.state,
                "attributes": {
                    k: v
                    for k, v in {
                        "brightness": e.state.brightness,
                        "position": e.state.position,
                        "temperature": e.state.temperature,
                    }.items()
                    if v is not None
                },
            }
            for e in entities
        ],
        total=len(entities),
    )


@router.get("/mock-ha/history", response_model=MockHAServiceHistoryResponse)
async def get_mock_ha_service_history() -> MockHAServiceHistoryResponse:
    """Get mock HA service call history.

    Shows all service calls made during the test session.
    Useful for verifying that action commands were executed correctly.
    """
    mock_ha = get_mock_ha()
    history = mock_ha.get_service_call_history()

    return MockHAServiceHistoryResponse(
        calls=[
            {
                "timestamp": call.timestamp.isoformat(),
                "domain": call.domain,
                "service": call.service,
                "entity_id": call.entity_id,
                "area_id": call.area_id,
                "data": call.data,
                "success": call.result.success,
                "message": call.result.message,
            }
            for call in history
        ],
        total=len(history),
    )
