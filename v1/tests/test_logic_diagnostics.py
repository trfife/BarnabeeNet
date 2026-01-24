"""Tests for Logic Diagnostics Service.

Tests the pattern matching diagnostics including:
- Near-miss detection
- Failure reason identification
- Pattern suggestions
"""

import re

import pytest

from barnabeenet.services.logic_diagnostics import (
    LogicDiagnosticsService,
    MatchFailureReason,
    PatternCheckResult,
    PatternDiagnostics,
    get_diagnostics_service,
)


class TestLogicDiagnosticsService:
    """Test suite for LogicDiagnosticsService."""

    @pytest.fixture
    def diagnostics_service(self) -> LogicDiagnosticsService:
        """Create a fresh diagnostics service."""
        return LogicDiagnosticsService()

    @pytest.fixture
    def sample_patterns(self) -> dict[str, list[tuple[re.Pattern[str], str]]]:
        """Create sample patterns for testing."""
        return {
            "action": [
                (re.compile(r"^turn\s+(on|off)\s+(the\s+)?(.+)$", re.IGNORECASE), "device_control"),
                (
                    re.compile(r"^switch\s+(on|off)\s+(the\s+)?(.+)$", re.IGNORECASE),
                    "device_control",
                ),
                (re.compile(r"^set\s+(.+)\s+to\s+(\d+).*$", re.IGNORECASE), "set_value"),
            ],
            "instant": [
                (re.compile(r"^what\s+time\s+is\s+it\??$", re.IGNORECASE), "time"),
                (re.compile(r"^what('s|.is)\s+the\s+date\??$", re.IGNORECASE), "date"),
            ],
            "memory": [
                (re.compile(r"^(please\s+)?remember\s+(.+)$", re.IGNORECASE), "store"),
                (re.compile(r"^do\s+you\s+remember\s+(.+)\??$", re.IGNORECASE), "recall"),
            ],
        }

    @pytest.fixture
    def pattern_priority(self) -> list[tuple[str, str, float]]:
        """Create pattern priority for testing."""
        return [
            ("instant", "INSTANT", 0.95),
            ("action", "ACTION", 0.90),
            ("memory", "MEMORY", 0.90),
        ]

    def test_diagnose_exact_match(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that exact matches are found."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="turn on the living room light",
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        assert diag.winner is not None
        assert diag.winner.matched is True
        assert diag.winner.pattern_group == "action"
        assert diag.winner.sub_category == "device_control"
        assert diag.classification_method == "pattern"

    def test_diagnose_no_match(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that non-matching text is diagnosed."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="what's the weather like",
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        assert diag.winner is None
        assert diag.classification_method == "fallback"
        assert diag.total_patterns_checked > 0

    def test_diagnose_near_miss_typo(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that typos are detected in diagnostics."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="trun on the light",  # typo: trun instead of turn
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        # Should have all_checks with diagnostics
        assert len(diag.all_checks) > 0

        # Find the check for the "turn" pattern
        turn_check = next(
            (c for c in diag.all_checks if "turn" in c.pattern_str.lower()),
            None,
        )
        assert turn_check is not None
        # Should detect this as a typo
        from barnabeenet.services.logic_diagnostics import MatchFailureReason

        assert turn_check.failure_reason == MatchFailureReason.TYPO
        assert any("typo" in s.lower() for s in turn_check.suggestions)

    def test_diagnose_anchor_fail(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that anchor failures are detected."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="please turn on the light",  # Extra word at start
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        # Pattern "turn on" starts with ^, so this should fail due to "please" prefix
        assert diag.winner is None

        # Find the check for the device_control pattern
        turn_check = next(
            (c for c in diag.all_checks if "turn" in c.pattern_str),
            None,
        )
        assert turn_check is not None
        # Should detect anchor failure (extra words at start/end)
        assert turn_check.failure_reason == MatchFailureReason.ANCHOR_FAIL
        assert any(
            "anchor" in s.lower() or "start/end" in s.lower() for s in turn_check.suggestions
        )

    def test_diagnose_generates_suggestions(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that pattern suggestions are generated."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="turn off all lights downstairs",  # More complex command
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        # Should either match or generate suggestions
        if diag.winner is None:
            assert len(diag.suggested_patterns) > 0 or len(diag.near_misses) > 0

    def test_pattern_check_result_structure(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that PatternCheckResult has expected structure."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="what time is it",
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        assert isinstance(diag, PatternDiagnostics)
        assert diag.input_text == "what time is it"
        assert diag.normalized_text == "what time is it"
        assert diag.processing_time_ms >= 0

        if diag.winner:
            assert isinstance(diag.winner, PatternCheckResult)
            assert diag.winner.pattern_str != ""
            assert diag.winner.pattern_group in sample_patterns

    def test_stats_tracking(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that stats are tracked correctly."""
        # Run several diagnoses
        for text in ["what time is it", "turn on the light", "unknown command"]:
            diagnostics_service.diagnose_pattern_match(
                text=text,
                compiled_patterns=sample_patterns,
                pattern_priority=pattern_priority,
            )

        stats = diagnostics_service.get_stats()
        assert stats["total_diagnoses"] == 3
        assert "pattern_match_rate" in stats
        assert "failure_rate" in stats

    def test_recent_failures_tracking(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that failures are tracked separately."""
        # Run a failing diagnosis
        diagnostics_service.diagnose_pattern_match(
            text="completely unknown command that matches nothing",
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        failures = diagnostics_service.get_recent_failures(limit=10)
        assert len(failures) >= 1
        assert failures[-1].winner is None

    def test_singleton_pattern(self):
        """Test that get_diagnostics_service returns singleton."""
        service1 = get_diagnostics_service()
        service2 = get_diagnostics_service()
        assert service1 is service2

    def test_to_dict_serialization(
        self,
        diagnostics_service: LogicDiagnosticsService,
        sample_patterns: dict,
        pattern_priority: list,
    ):
        """Test that diagnostics can be serialized."""
        diag = diagnostics_service.diagnose_pattern_match(
            text="turn on the kitchen light",
            compiled_patterns=sample_patterns,
            pattern_priority=pattern_priority,
        )

        result = diag.to_dict()
        assert "input_text" in result
        assert "normalized_text" in result
        assert "timestamp" in result
        assert "total_patterns_checked" in result
        assert "classification_method" in result

        if diag.winner:
            assert result["winner"] is not None
            assert "pattern" in result["winner"]
            assert "group" in result["winner"]


class TestMatchFailureReasons:
    """Test failure reason detection."""

    @pytest.fixture
    def diagnostics_service(self) -> LogicDiagnosticsService:
        return LogicDiagnosticsService()

    def test_edit_distance_calculation(self, diagnostics_service: LogicDiagnosticsService):
        """Test edit distance is calculated correctly."""
        # Exact match
        assert diagnostics_service._edit_distance("turn", "turn") == 0
        # One deletion
        assert diagnostics_service._edit_distance("turn", "tun") == 1
        # One substitution
        assert diagnostics_service._edit_distance("turn", "tarn") == 1
        # Two edits
        assert diagnostics_service._edit_distance("turn", "run") == 2

    def test_typo_detection(self, diagnostics_service: LogicDiagnosticsService):
        """Test typo detection."""
        # Known typos
        assert diagnostics_service._is_likely_typo("turn", {"trun"})
        assert diagnostics_service._is_likely_typo("switch", {"swich"})
        assert diagnostics_service._is_likely_typo("light", {"lihgt"})

        # Not typos
        assert not diagnostics_service._is_likely_typo("turn", {"walk"})

    def test_keyword_extraction(self, diagnostics_service: LogicDiagnosticsService):
        """Test keyword extraction from patterns."""
        keywords = diagnostics_service._extract_keywords(r"^turn\s+(on|off)\s+the\s+(.+)$")
        assert "turn" in keywords
        # 'on', 'off', 'the' might be filtered as common words

    def test_similarity_calculation(self, diagnostics_service: LogicDiagnosticsService):
        """Test similarity scoring."""
        pattern = re.compile(r"^turn on the light$", re.IGNORECASE)

        # Exact-ish match should have high similarity
        sim1 = diagnostics_service._calculate_similarity("turn on the light", pattern)
        assert sim1 > 0.9

        # Different text should have lower similarity
        sim2 = diagnostics_service._calculate_similarity("open the door", pattern)
        assert sim2 < sim1


class TestPatternSuggestions:
    """Test pattern suggestion generation."""

    @pytest.fixture
    def diagnostics_service(self) -> LogicDiagnosticsService:
        return LogicDiagnosticsService()

    def test_command_suggestions(self, diagnostics_service: LogicDiagnosticsService):
        """Test that command patterns generate suggestions."""
        suggestions = diagnostics_service._generate_pattern_suggestions("turn on the bedroom light")
        assert len(suggestions) > 0
        # Should suggest a pattern starting with 'turn'
        assert any("turn" in s.lower() for s in suggestions)

    def test_question_suggestions(self, diagnostics_service: LogicDiagnosticsService):
        """Test that question patterns generate suggestions."""
        suggestions = diagnostics_service._generate_pattern_suggestions("what is the temperature?")
        assert len(suggestions) > 0
        # Should suggest a pattern starting with 'what'
        assert any("what" in s.lower() for s in suggestions)

    def test_memory_suggestions(self, diagnostics_service: LogicDiagnosticsService):
        """Test that memory-related text generates suggestions."""
        suggestions = diagnostics_service._generate_pattern_suggestions(
            "remember my favorite color is blue"
        )
        assert len(suggestions) > 0
        # Should suggest a pattern with 'remember'
        assert any("remember" in s.lower() for s in suggestions)
