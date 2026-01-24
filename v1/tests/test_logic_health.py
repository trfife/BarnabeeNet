"""Tests for Logic Health Monitor.

Tests the health monitoring capabilities including:
- Classification recording
- Consistency checking
- Issue detection
- Health report generation
"""

import pytest

from barnabeenet.services.logic_health import (
    ClassificationRecord,
    HealthIssue,
    HealthIssueType,
    HealthReport,
    IssueSeverity,
    LogicHealthMonitor,
    get_health_monitor,
    reset_health_monitor,
)


@pytest.fixture(autouse=True)
def reset_monitor():
    """Reset the health monitor before each test."""
    reset_health_monitor()
    yield
    reset_health_monitor()


class TestLogicHealthMonitor:
    """Tests for LogicHealthMonitor class."""

    def test_record_classification(self):
        """Test that classifications are recorded."""
        monitor = LogicHealthMonitor()
        monitor.record_classification(
            raw_input="what time is it",
            intent="instant",
            sub_category="time",
            confidence=0.95,
            classification_method="pattern",
            matched_pattern="instant:time",
        )

        stats = monitor.get_stats()
        assert stats["total_classifications"] == 1
        assert stats["unique_inputs"] == 1

    def test_consistent_classification(self):
        """Test that consistent classifications are recognized."""
        monitor = LogicHealthMonitor()

        # Same input, same result - should be consistent
        for _ in range(3):
            monitor.record_classification(
                raw_input="what time is it",
                intent="instant",
                sub_category="time",
                confidence=0.95,
                classification_method="pattern",
            )

        # Check consistency
        input_hash = monitor._hash_input("what time is it")
        is_consistent, conflicts = monitor.check_consistency(input_hash)
        assert is_consistent is True
        assert len(conflicts) == 0

    def test_inconsistent_classification(self):
        """Test that inconsistent classifications are detected."""
        monitor = LogicHealthMonitor()

        # Same input, different results - should be inconsistent
        monitor.record_classification(
            raw_input="play some music",
            intent="action",
            sub_category="media_control",
            confidence=0.85,
            classification_method="pattern",
        )
        monitor.record_classification(
            raw_input="play some music",
            intent="conversation",
            sub_category=None,
            confidence=0.60,
            classification_method="llm",
        )

        input_hash = monitor._hash_input("play some music")
        is_consistent, conflicts = monitor.check_consistency(input_hash)
        assert is_consistent is False
        assert len(conflicts) == 1

    def test_normalization_consistency(self):
        """Test that text normalization works for consistency."""
        monitor = LogicHealthMonitor()

        # Different formatting, same content (after normalization)
        monitor.record_classification(
            raw_input="What Time Is It",
            intent="instant",
            sub_category="time",
            confidence=0.95,
            classification_method="pattern",
        )
        monitor.record_classification(
            raw_input="  what  time  is  it  ",
            intent="instant",
            sub_category="time",
            confidence=0.95,
            classification_method="pattern",
        )

        stats = monitor.get_stats()
        assert stats["unique_inputs"] == 1  # Both should hash to same input
        assert stats["total_classifications"] == 2

    def test_method_tracking(self):
        """Test that classification methods are tracked."""
        monitor = LogicHealthMonitor()

        # Record with different methods
        monitor.record_classification(
            raw_input="turn on the light",
            intent="action",
            sub_category="device_control",
            confidence=0.90,
            classification_method="pattern",
        )
        monitor.record_classification(
            raw_input="tell me a story",
            intent="conversation",
            sub_category=None,
            confidence=0.75,
            classification_method="heuristic",
        )
        monitor.record_classification(
            raw_input="what's the meaning of life",
            intent="conversation",
            sub_category=None,
            confidence=0.80,
            classification_method="llm",
        )

        stats = monitor.get_stats()
        assert stats["method_counts"]["pattern"] == 1
        assert stats["method_counts"]["heuristic"] == 1
        assert stats["method_counts"]["llm"] == 1

    def test_near_miss_tracking(self):
        """Test that near misses are tracked."""
        monitor = LogicHealthMonitor()

        # Record with near misses
        for _ in range(5):
            monitor.record_classification(
                raw_input="please turn on light",
                intent="action",
                sub_category="device_control",
                confidence=0.50,
                classification_method="heuristic",
                near_misses=[{"pattern_str": "^turn on the light$"}],
            )

        near_misses = monitor.get_frequent_near_misses(min_count=3)
        assert len(near_misses) >= 1

    def test_health_report_generation(self):
        """Test health report generation."""
        monitor = LogicHealthMonitor()

        # Add some data
        for i in range(10):
            monitor.record_classification(
                raw_input=f"test input {i}",
                intent="instant",
                sub_category="time",
                confidence=0.9,
                classification_method="pattern",
            )

        report = monitor.generate_health_report()
        assert report.total_classifications == 10
        assert report.unique_inputs == 10
        assert report.consistency_score == 1.0  # All consistent
        assert report.avg_confidence > 0

    def test_health_report_with_issues(self):
        """Test that health report detects issues."""
        monitor = LogicHealthMonitor()

        # Create inconsistent classification
        monitor.record_classification(
            raw_input="test input",
            intent="instant",
            sub_category="time",
            confidence=0.95,
            classification_method="pattern",
        )
        monitor.record_classification(
            raw_input="test input",
            intent="action",
            sub_category="device_control",
            confidence=0.80,
            classification_method="heuristic",
        )

        report = monitor.generate_health_report()
        assert report.consistency_score < 1.0
        assert len(report.issues) > 0

        # Should have inconsistent classification issue
        issue_types = [i.issue_type for i in report.issues]
        assert HealthIssueType.INCONSISTENT_CLASSIFICATION in issue_types

    def test_clear(self):
        """Test that clear removes all data."""
        monitor = LogicHealthMonitor()

        # Add data
        monitor.record_classification(
            raw_input="test",
            intent="instant",
            sub_category="time",
            confidence=0.95,
            classification_method="pattern",
        )

        # Clear
        monitor.clear()

        stats = monitor.get_stats()
        assert stats["total_classifications"] == 0
        assert stats["unique_inputs"] == 0

    def test_singleton_pattern(self):
        """Test that get_health_monitor returns singleton."""
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()
        assert monitor1 is monitor2


class TestHealthReport:
    """Tests for HealthReport serialization."""

    def test_to_dict(self):
        """Test that HealthReport serializes correctly."""
        report = HealthReport(
            total_classifications=100,
            unique_inputs=50,
            consistency_score=0.95,
            avg_confidence=0.85,
            pattern_match_rate=0.70,
            heuristic_rate=0.20,
            llm_fallback_rate=0.10,
        )

        data = report.to_dict()
        assert data["total_classifications"] == 100
        assert data["consistency_score"] == 0.95
        assert "generated_at" in data
        assert "issues_by_severity" in data


class TestHealthIssue:
    """Tests for HealthIssue serialization."""

    def test_to_dict(self):
        """Test that HealthIssue serializes correctly."""
        issue = HealthIssue(
            issue_type=HealthIssueType.INCONSISTENT_CLASSIFICATION,
            severity=IssueSeverity.WARNING,
            title="Test Issue",
            description="This is a test",
            affected_inputs=["test input"],
            suggested_action="Fix it",
        )

        data = issue.to_dict()
        assert data["issue_type"] == "inconsistent_classification"
        assert data["severity"] == "warning"
        assert data["title"] == "Test Issue"


class TestClassificationRecord:
    """Tests for ClassificationRecord serialization."""

    def test_to_dict(self):
        """Test that ClassificationRecord serializes correctly."""
        record = ClassificationRecord(
            input_hash="abc123",
            raw_input="test input",
            normalized_input="test input",
            intent="instant",
            sub_category="time",
            confidence=0.95,
            classification_method="pattern",
            matched_pattern="instant:time",
        )

        data = record.to_dict()
        assert data["intent"] == "instant"
        assert data["confidence"] == 0.95
        assert "timestamp" in data
