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
