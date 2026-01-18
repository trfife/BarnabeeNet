"""Tests for E2E testing endpoints and framework."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from barnabeenet.services.e2e_tester import (
    AssertionType,
    E2ETestRunner,
    TestAssertion,
    TestCase,
    TestCategory,
    TestResult,
    TestSuiteConfig,
    get_test_runner,
)


class TestE2ETestRunner:
    """Tests for E2ETestRunner class."""

    def test_get_test_runner_singleton(self):
        """Test that get_test_runner returns the same instance."""
        runner1 = get_test_runner()
        runner2 = get_test_runner()
        assert runner1 is runner2

    def test_get_available_tests(self):
        """Test that available tests are returned."""
        runner = E2ETestRunner()
        tests = runner.get_available_tests()

        assert len(tests) > 0
        assert all("id" in t for t in tests)
        assert all("name" in t for t in tests)
        assert all("category" in t for t in tests)

    def test_available_tests_have_required_fields(self):
        """Test that all available tests have required fields."""
        runner = E2ETestRunner()
        tests = runner.get_available_tests()

        for test in tests:
            assert "id" in test
            assert "name" in test
            assert "description" in test
            assert "category" in test
            assert "input_text" in test
            assert "assertion_count" in test

    def test_select_tests_all_categories(self):
        """Test that all tests are selected when no filter is applied."""
        runner = E2ETestRunner()
        config = TestSuiteConfig(categories=None, include_llm_tests=True)
        tests = runner._select_tests(config)

        assert len(tests) > 0

    def test_select_tests_instant_only(self):
        """Test filtering to instant tests only."""
        runner = E2ETestRunner()
        config = TestSuiteConfig(categories=[TestCategory.INSTANT])
        tests = runner._select_tests(config)

        assert len(tests) > 0
        assert all(t.category == TestCategory.INSTANT for t in tests)

    def test_select_tests_excludes_llm_by_default(self):
        """Test that LLM tests are excluded by default."""
        runner = E2ETestRunner()
        config = TestSuiteConfig(include_llm_tests=False)
        tests = runner._select_tests(config)

        assert all(t.category != TestCategory.INTERACTION for t in tests)


class TestAssertionEvaluation:
    """Tests for assertion evaluation logic."""

    def test_evaluate_agent_used_pass(self):
        """Test agent_used assertion passes."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.agent_used = "instant"

        assertion = TestAssertion(type=AssertionType.AGENT_USED, expected="instant")
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is True
        assert assertion.actual == "instant"

    def test_evaluate_agent_used_fail(self):
        """Test agent_used assertion fails."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.agent_used = "interaction"

        assertion = TestAssertion(type=AssertionType.AGENT_USED, expected="instant")
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is False

    def test_evaluate_response_contains_pass(self):
        """Test response_contains assertion passes."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.response_text = "The answer is 42"

        assertion = TestAssertion(type=AssertionType.RESPONSE_CONTAINS, expected="42")
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is True

    def test_evaluate_response_contains_fail(self):
        """Test response_contains assertion fails."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.response_text = "The answer is fifty"

        assertion = TestAssertion(type=AssertionType.RESPONSE_CONTAINS, expected="42")
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is False

    def test_evaluate_latency_under_pass(self):
        """Test latency_under assertion passes."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.latency_ms = 100

        assertion = TestAssertion(type=AssertionType.LATENCY_UNDER, expected=500)
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is True

    def test_evaluate_latency_under_fail(self):
        """Test latency_under assertion fails."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.latency_ms = 1000

        assertion = TestAssertion(type=AssertionType.LATENCY_UNDER, expected=500)
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is False

    def test_evaluate_no_error_pass(self):
        """Test no_error assertion passes when no error."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.error = None

        assertion = TestAssertion(type=AssertionType.NO_ERROR, expected=True)
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is True

    def test_evaluate_no_error_fail(self):
        """Test no_error assertion fails when error exists."""
        runner = E2ETestRunner()
        test = TestCase(
            id="test1",
            name="Test",
            description="Test",
            category=TestCategory.INSTANT,
            input_text="test",
        )
        test.error = "Something went wrong"

        assertion = TestAssertion(type=AssertionType.NO_ERROR, expected=True)
        runner._evaluate_assertion(test, assertion)

        assert assertion.passed is False


class TestE2ERoutes:
    """Tests for E2E API routes."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient

        from barnabeenet.main import app

        return TestClient(app)

    def test_list_available_tests(self, client):
        """Test listing available tests."""
        response = client.get("/api/v1/e2e/tests")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "categories" in data
        assert "tests" in data
        assert data["total"] > 0

    def test_list_categories(self, client):
        """Test listing test categories."""
        response = client.get("/api/v1/e2e/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) > 0

    @pytest.mark.asyncio
    async def test_run_suite_mocked(self):
        """Test running a test suite with mocked orchestrator."""
        from fastapi.testclient import TestClient

        from barnabeenet.main import app

        # Mock orchestrator process to return instant agent response
        mock_response = {
            "response": "It is 3:00 PM.",
            "agent": "instant",
            "intent": "instant",
            "trace_id": "test-trace-123",
        }

        with patch("barnabeenet.agents.orchestrator.get_orchestrator") as mock_get_orchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process = AsyncMock(return_value=mock_response)
            mock_get_orchestrator.return_value = mock_orchestrator

            client = TestClient(app)
            response = client.post(
                "/api/v1/e2e/run",
                json={
                    "suite_name": "test_run",
                    "categories": ["instant"],
                    "include_llm_tests": False,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "suite_id" in data
        assert data["total_tests"] > 0


class TestTestCase:
    """Tests for TestCase dataclass."""

    def test_test_case_defaults(self):
        """Test TestCase default values."""
        test = TestCase(
            id="test1",
            name="Test",
            description="A test",
            category=TestCategory.INSTANT,
            input_text="hello",
        )

        assert test.speaker == "e2e_test"
        assert test.room == "test_room"
        assert test.result == TestResult.SKIP
        assert test.assertions == []

    def test_test_case_with_assertions(self):
        """Test TestCase with assertions."""
        assertions = [
            TestAssertion(type=AssertionType.AGENT_USED, expected="instant"),
            TestAssertion(type=AssertionType.NO_ERROR, expected=True),
        ]

        test = TestCase(
            id="test1",
            name="Test",
            description="A test",
            category=TestCategory.INSTANT,
            input_text="hello",
            assertions=assertions,
        )

        assert len(test.assertions) == 2


class TestTestSuiteConfig:
    """Tests for TestSuiteConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TestSuiteConfig()

        assert config.suite_name == "default"
        assert config.categories is None
        assert config.include_llm_tests is False
        assert config.delay_between_tests_ms == 100

    def test_custom_config(self):
        """Test custom configuration."""
        config = TestSuiteConfig(
            suite_name="custom",
            categories=[TestCategory.INSTANT, TestCategory.ACTION],
            include_llm_tests=True,
            delay_between_tests_ms=200,
        )

        assert config.suite_name == "custom"
        assert len(config.categories) == 2
        assert config.include_llm_tests is True
        assert config.delay_between_tests_ms == 200
