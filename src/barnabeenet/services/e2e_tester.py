"""End-to-end voice pipeline testing service.

Provides automated testing of the full BarnabeeNet pipeline from text input
through agent processing, with results logged to the dashboard for visibility.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TestCategory(str, Enum):
    """Categories of E2E tests."""

    INSTANT = "instant"  # Time, date, greetings, math
    ACTION = "action"  # Device control commands
    INTERACTION = "interaction"  # Conversations requiring LLM
    MEMORY = "memory"  # Memory storage/retrieval
    PIPELINE = "pipeline"  # Full pipeline flow


class AssertionType(str, Enum):
    """Types of assertions for test validation."""

    AGENT_USED = "agent_used"  # Verify correct agent handled request
    INTENT = "intent"  # Verify intent classification
    RESPONSE_CONTAINS = "response_contains"  # Response includes text
    RESPONSE_NOT_CONTAINS = "response_not_contains"  # Response excludes text
    LATENCY_UNDER = "latency_under"  # Response time threshold
    NO_ERROR = "no_error"  # Request succeeded
    ENTITY_STATE = "entity_state"  # Verify mock HA entity state after action


class TestResult(str, Enum):
    """Result of a test execution."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class TestAssertion:
    """A single assertion to validate."""

    type: AssertionType
    expected: Any
    actual: Any | None = None
    passed: bool = False
    message: str = ""


@dataclass
class TestCase:
    """Definition of an E2E test case."""

    id: str
    name: str
    description: str
    category: TestCategory
    input_text: str
    speaker: str = "e2e_test"
    room: str = "test_room"
    assertions: list[TestAssertion] = field(default_factory=list)

    # Results
    result: TestResult = TestResult.SKIP
    response_text: str = ""
    agent_used: str = ""
    intent: str = ""
    latency_ms: float = 0.0
    trace_id: str = ""
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TestSuiteConfig(BaseModel):
    """Configuration for a test suite run."""

    suite_name: str = Field(default="default", description="Name of the test suite")
    categories: list[TestCategory] | None = Field(
        default=None, description="Filter by categories (None = all)"
    )
    include_llm_tests: bool = Field(
        default=False, description="Include tests that require LLM calls"
    )
    delay_between_tests_ms: int = Field(default=100, description="Delay between test executions")
    use_mock_ha: bool = Field(
        default=True,
        description="Use mock Home Assistant for action tests (no real HA needed)",
    )


class TestSuiteResult(BaseModel):
    """Results of a complete test suite run."""

    suite_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    suite_name: str
    started_at: datetime
    completed_at: datetime | None = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total_latency_ms: float = 0.0
    test_results: list[dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Built-in Test Cases
# =============================================================================

INSTANT_TESTS: list[TestCase] = [
    TestCase(
        id="instant_time",
        name="Time Query",
        description="Ask for current time - should route to InstantAgent",
        category=TestCategory.INSTANT,
        input_text="What time is it?",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="instant"),
            TestAssertion(type=AssertionType.INTENT, expected="instant"),
            TestAssertion(type=AssertionType.LATENCY_UNDER, expected=500),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
    TestCase(
        id="instant_date",
        name="Date Query",
        description="Ask for current date - should route to InstantAgent",
        category=TestCategory.INSTANT,
        input_text="What's today's date?",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="instant"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
    TestCase(
        id="instant_greeting_hello",
        name="Hello Greeting",
        description="Simple greeting should route to InstantAgent",
        category=TestCategory.INSTANT,
        input_text="Hello Barnabee",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="instant"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
    TestCase(
        id="instant_math_add",
        name="Math Addition",
        description="Basic math should route to InstantAgent",
        category=TestCategory.INSTANT,
        input_text="What's 15 plus 27?",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="instant"),
            TestAssertion(type=AssertionType.RESPONSE_CONTAINS, expected="42"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
    TestCase(
        id="instant_math_multiply",
        name="Math Multiplication",
        description="Multiplication should route to InstantAgent",
        category=TestCategory.INSTANT,
        input_text="What is 7 times 8?",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="instant"),
            TestAssertion(type=AssertionType.RESPONSE_CONTAINS, expected="56"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
]

ACTION_TESTS: list[TestCase] = [
    TestCase(
        id="action_light_on",
        name="Turn Light On",
        description="Light control should route to ActionAgent and turn on living room light",
        category=TestCategory.ACTION,
        input_text="Turn on the living room light",
        room="living_room",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="action"),
            TestAssertion(type=AssertionType.INTENT, expected="action"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
            TestAssertion(
                type=AssertionType.ENTITY_STATE,
                expected={"entity_id": "light.living_room_main", "state": "on"},
            ),
        ],
    ),
    TestCase(
        id="action_light_off",
        name="Turn Light Off",
        description="Light off command should route to ActionAgent and turn off kitchen light",
        category=TestCategory.ACTION,
        input_text="Switch off the kitchen light",
        room="kitchen",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="action"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
            TestAssertion(
                type=AssertionType.ENTITY_STATE,
                expected={"entity_id": "light.kitchen_main", "state": "off"},
            ),
        ],
    ),
    TestCase(
        id="action_lamp_brightness",
        name="Set Lamp Brightness",
        description="Brightness control should work via ActionAgent",
        category=TestCategory.ACTION,
        input_text="Set the living room lamp to 50 percent",
        room="living_room",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="action"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
    TestCase(
        id="action_close_blinds",
        name="Close Blinds",
        description="Cover control should route to ActionAgent",
        category=TestCategory.ACTION,
        input_text="Close the living room blinds",
        room="living_room",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="action"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
            TestAssertion(
                type=AssertionType.ENTITY_STATE,
                expected={"entity_id": "cover.living_room_blinds", "state": "closed"},
            ),
        ],
    ),
]

INTERACTION_TESTS: list[TestCase] = [
    TestCase(
        id="interaction_question",
        name="General Question",
        description="Complex question should route to InteractionAgent",
        category=TestCategory.INTERACTION,
        input_text="Tell me about the history of artificial intelligence",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="interaction"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
    TestCase(
        id="interaction_barnabee_identity",
        name="Barnabee Identity",
        description="Ask who Barnabee is - should respond in character",
        category=TestCategory.INTERACTION,
        input_text="Who are you?",
        assertions=[
            TestAssertion(type=AssertionType.AGENT_USED, expected="interaction"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ],
    ),
]

ALL_TESTS: list[TestCase] = INSTANT_TESTS + ACTION_TESTS + INTERACTION_TESTS


# =============================================================================
# E2E Test Runner
# =============================================================================


class E2ETestRunner:
    """Executes E2E tests and logs results to dashboard."""

    def __init__(self) -> None:
        self._running = False
        self._current_suite: TestSuiteResult | None = None

    async def run_suite(
        self,
        config: TestSuiteConfig | None = None,
    ) -> TestSuiteResult:
        """Run a test suite based on configuration."""
        from barnabeenet.services.pipeline_signals import (
            PipelineSignal,
            SignalType,
            get_pipeline_logger,
        )

        if config is None:
            config = TestSuiteConfig()

        pipeline_logger = get_pipeline_logger()

        # Select tests based on config
        tests = self._select_tests(config)

        # Set up mock HA if enabled (for action tests without real HA)
        mock_client = None
        if config.use_mock_ha:
            from barnabeenet.agents.orchestrator import get_orchestrator
            from barnabeenet.services.homeassistant.mock_ha import (
                enable_mock_ha,
                get_mock_ha_client,
                reset_mock_ha,
            )

            # Reset mock to clean state and enable it
            reset_mock_ha()
            enable_mock_ha()
            mock_client = get_mock_ha_client()

            # Inject mock client into orchestrator
            orchestrator = get_orchestrator()
            orchestrator.set_ha_client(mock_client)  # type: ignore[arg-type]
            logger.info("Mock HA enabled for E2E tests")

        suite = TestSuiteResult(
            suite_name=config.suite_name,
            started_at=datetime.now(UTC),
            total_tests=len(tests),
        )
        self._current_suite = suite
        self._running = True

        # Log test suite start
        await pipeline_logger.log_signal(
            PipelineSignal(
                trace_id=suite.suite_id,
                signal_type=SignalType.E2E_TEST_START,
                stage="test",
                component="e2e_runner",
                summary=f"E2E Test Suite '{config.suite_name}' started with {len(tests)} tests",
                input_data={
                    "suite_name": config.suite_name,
                    "total_tests": len(tests),
                    "categories": [c.value for c in (config.categories or [])],
                },
            )
        )

        # Run each test
        for test in tests:
            if not self._running:
                break

            result = await self._run_test(test, suite.suite_id)
            suite.test_results.append(self._test_to_dict(result))
            suite.total_latency_ms += result.latency_ms

            # Update counts
            if result.result == TestResult.PASS:
                suite.passed += 1
            elif result.result == TestResult.FAIL:
                suite.failed += 1
            elif result.result == TestResult.ERROR:
                suite.errors += 1
            else:
                suite.skipped += 1

            # Delay between tests
            if config.delay_between_tests_ms > 0:
                await asyncio.sleep(config.delay_between_tests_ms / 1000)

        suite.completed_at = datetime.now(UTC)
        self._running = False

        # Clean up mock HA if it was enabled
        if config.use_mock_ha:
            from barnabeenet.agents.orchestrator import get_orchestrator
            from barnabeenet.services.homeassistant.mock_ha import disable_mock_ha

            # Clear the mock client from orchestrator
            orchestrator = get_orchestrator()
            orchestrator.set_ha_client(None)
            disable_mock_ha()
            logger.info("Mock HA disabled after E2E tests")

        # Log test suite completion
        await pipeline_logger.log_signal(
            PipelineSignal(
                trace_id=suite.suite_id,
                signal_type=SignalType.E2E_TEST_COMPLETE,
                stage="test",
                component="e2e_runner",
                success=suite.failed == 0 and suite.errors == 0,
                latency_ms=suite.total_latency_ms,
                summary=f"E2E Suite complete: {suite.passed}/{suite.total_tests} passed",
                output_data={
                    "passed": suite.passed,
                    "failed": suite.failed,
                    "errors": suite.errors,
                    "skipped": suite.skipped,
                },
            )
        )

        return suite

    async def run_single_test(self, test_id: str) -> TestCase | None:
        """Run a single test by ID."""
        for test in ALL_TESTS:
            if test.id == test_id:
                return await self._run_test(test, str(uuid.uuid4()))
        return None

    def _select_tests(self, config: TestSuiteConfig) -> list[TestCase]:
        """Select tests based on configuration."""
        tests = ALL_TESTS.copy()

        # Filter by category
        if config.categories:
            tests = [t for t in tests if t.category in config.categories]

        # Exclude LLM tests if not enabled
        if not config.include_llm_tests:
            tests = [t for t in tests if t.category != TestCategory.INTERACTION]

        return tests

    async def _run_test(self, test: TestCase, suite_id: str) -> TestCase:
        """Execute a single test case."""
        from barnabeenet.agents.orchestrator import get_orchestrator
        from barnabeenet.services.pipeline_signals import (
            PipelineSignal,
            SignalType,
            get_pipeline_logger,
        )

        pipeline_logger = get_pipeline_logger()
        test.started_at = datetime.now(UTC)

        # Log test step
        await pipeline_logger.log_signal(
            PipelineSignal(
                trace_id=suite_id,
                signal_type=SignalType.E2E_TEST_STEP,
                stage="test",
                component="e2e_runner",
                summary=f"Running test: {test.name}",
                input_data={
                    "test_id": test.id,
                    "test_name": test.name,
                    "input_text": test.input_text,
                    "category": test.category.value,
                },
            )
        )

        try:
            start_time = time.perf_counter()

            # Execute through orchestrator
            orchestrator = get_orchestrator()
            response = await orchestrator.process(
                text=test.input_text,
                speaker=test.speaker,
                room=test.room,
            )

            test.latency_ms = (time.perf_counter() - start_time) * 1000
            test.response_text = response.get("response", "")
            test.agent_used = response.get("agent", "unknown")
            test.intent = response.get("intent", "unknown")
            test.trace_id = response.get("trace_id", "")
            test.completed_at = datetime.now(UTC)

            # Run assertions
            all_passed = True
            for assertion in test.assertions:
                self._evaluate_assertion(test, assertion)
                if not assertion.passed:
                    all_passed = False

                # Log assertion result
                await pipeline_logger.log_signal(
                    PipelineSignal(
                        trace_id=suite_id,
                        signal_type=(
                            SignalType.E2E_ASSERTION_PASS
                            if assertion.passed
                            else SignalType.E2E_ASSERTION_FAIL
                        ),
                        stage="test",
                        component="e2e_runner",
                        success=assertion.passed,
                        summary=f"{assertion.type.value}: {assertion.message}",
                        input_data={
                            "test_id": test.id,
                            "assertion_type": assertion.type.value,
                            "expected": str(assertion.expected),
                            "actual": str(assertion.actual),
                        },
                    )
                )

            test.result = TestResult.PASS if all_passed else TestResult.FAIL

        except Exception as e:
            test.completed_at = datetime.now(UTC)
            test.latency_ms = (time.perf_counter() - start_time) * 1000
            test.result = TestResult.ERROR
            test.error = str(e)
            logger.error("Test execution error", extra={"test_id": test.id, "error": str(e)})

        return test

    def _evaluate_assertion(self, test: TestCase, assertion: TestAssertion) -> None:
        """Evaluate a single assertion against test results."""
        try:
            if assertion.type == AssertionType.AGENT_USED:
                assertion.actual = test.agent_used
                assertion.passed = test.agent_used == assertion.expected
                assertion.message = (
                    f"Expected agent '{assertion.expected}', got '{test.agent_used}'"
                )

            elif assertion.type == AssertionType.INTENT:
                assertion.actual = test.intent
                assertion.passed = test.intent == assertion.expected
                assertion.message = f"Expected intent '{assertion.expected}', got '{test.intent}'"

            elif assertion.type == AssertionType.RESPONSE_CONTAINS:
                assertion.actual = test.response_text[:100]
                assertion.passed = str(assertion.expected).lower() in test.response_text.lower()
                assertion.message = f"Response {'contains' if assertion.passed else 'missing'} '{assertion.expected}'"

            elif assertion.type == AssertionType.RESPONSE_NOT_CONTAINS:
                assertion.actual = test.response_text[:100]
                assertion.passed = str(assertion.expected).lower() not in test.response_text.lower()
                assertion.message = (
                    f"Response {'correctly excludes' if assertion.passed else 'incorrectly contains'} "
                    f"'{assertion.expected}'"
                )

            elif assertion.type == AssertionType.LATENCY_UNDER:
                assertion.actual = test.latency_ms
                assertion.passed = test.latency_ms < assertion.expected
                assertion.message = (
                    f"Latency {test.latency_ms:.0f}ms "
                    f"{'under' if assertion.passed else 'exceeds'} {assertion.expected}ms threshold"
                )

            elif assertion.type == AssertionType.NO_ERROR:
                assertion.actual = test.error is None
                assertion.passed = test.error is None
                assertion.message = (
                    "No error occurred" if assertion.passed else f"Error: {test.error}"
                )

            elif assertion.type == AssertionType.ENTITY_STATE:
                # Check mock HA entity state - expected format: {"entity_id": X, "state": Y}
                from barnabeenet.services.homeassistant.mock_ha import get_mock_ha

                mock_ha = get_mock_ha()
                expected_data = assertion.expected
                if isinstance(expected_data, dict):
                    entity_id = expected_data.get("entity_id", "")
                    expected_state = expected_data.get("state", "")
                    entity = mock_ha.get_entity(entity_id)
                    if entity:
                        assertion.actual = entity.state.state
                        assertion.passed = entity.state.state == expected_state
                        assertion.message = (
                            f"Entity '{entity_id}' state is '{entity.state.state}' "
                            f"({'matches' if assertion.passed else 'expected'} '{expected_state}')"
                        )
                    else:
                        assertion.actual = None
                        assertion.passed = False
                        assertion.message = f"Entity '{entity_id}' not found in mock HA"
                else:
                    assertion.passed = False
                    assertion.message = "Invalid ENTITY_STATE assertion format"

        except Exception as e:
            assertion.passed = False
            assertion.message = f"Assertion evaluation error: {e}"

    def _test_to_dict(self, test: TestCase) -> dict[str, Any]:
        """Convert test case to dictionary for API response."""
        return {
            "id": test.id,
            "name": test.name,
            "description": test.description,
            "category": test.category.value,
            "input_text": test.input_text,
            "result": test.result.value,
            "response_text": test.response_text[:200] if test.response_text else "",
            "agent_used": test.agent_used,
            "intent": test.intent,
            "latency_ms": round(test.latency_ms, 2),
            "trace_id": test.trace_id,
            "error": test.error,
            "assertions": [
                {
                    "type": a.type.value,
                    "expected": str(a.expected),
                    "actual": str(a.actual),
                    "passed": a.passed,
                    "message": a.message,
                }
                for a in test.assertions
            ],
        }

    def get_available_tests(self) -> list[dict[str, Any]]:
        """Get list of available tests."""
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "input_text": t.input_text,
                "assertion_count": len(t.assertions),
            }
            for t in ALL_TESTS
        ]


# Global instance
_test_runner: E2ETestRunner | None = None


def get_test_runner() -> E2ETestRunner:
    """Get or create the global test runner instance."""
    global _test_runner
    if _test_runner is None:
        _test_runner = E2ETestRunner()
    return _test_runner
