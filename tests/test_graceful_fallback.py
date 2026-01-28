"""Tests for the graceful fallback service and wake word stripping."""

import re

import pytest

from barnabeenet.services.graceful_fallback import GracefulFallbackService

# Copy of the wake word pattern from orchestrator for testing
WAKE_WORD_PATTERN = re.compile(
    r"^(hey |hi |hello |okay |ok )?(barnabee|barney|barnaby)\s*[,.]?\s*",
    re.IGNORECASE,
)


class TestGracefulFallbackService:
    """Tests for GracefulFallbackService."""

    def test_is_failure_response_detects_couldnt_find(self):
        """Should detect 'I couldn't find' as a failure."""
        service = GracefulFallbackService()
        assert service.is_failure_response("I couldn't find a device called 'office light'.")

    def test_is_failure_response_detects_dont_know(self):
        """Should detect 'I don't know' as a failure."""
        service = GracefulFallbackService()
        assert service.is_failure_response("I don't know who that is.")

    def test_is_failure_response_detects_no_entities_affected(self):
        """Should detect 'No entities affected' as a failure."""
        service = GracefulFallbackService()
        assert service.is_failure_response("No entities affected - entity may not exist.")

    def test_is_failure_response_allows_normal_responses(self):
        """Should not flag normal successful responses."""
        service = GracefulFallbackService()
        assert not service.is_failure_response("It's 3:45 PM.")
        assert not service.is_failure_response("Turning on the office light.")
        assert not service.is_failure_response("Thom is at home.")

    def test_recent_commands_tracking(self):
        """Should track recent commands in a rolling buffer."""
        service = GracefulFallbackService()
        service.add_recent_command("turn on the light")
        service.add_recent_command("what time is it")
        assert len(service._recent_commands) == 2
        assert "turn on the light" in service._recent_commands

    def test_recent_commands_max_size(self):
        """Should limit recent commands to max size."""
        service = GracefulFallbackService()
        for i in range(10):
            service.add_recent_command(f"command {i}")
        assert len(service._recent_commands) == service._max_recent_commands


class TestWakeWordStripping:
    """Tests for wake word stripping."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("barnabee what time is it", "what time is it"),
            ("hey barnabee turn on the light", "turn on the light"),
            ("Barnabee, what's the weather", "what's the weather"),
            ("ok barnabee set a timer", "set a timer"),
            ("hello barnabee how are you", "how are you"),
            ("barney what time is it", "what time is it"),
            ("barnaby turn off the fan", "turn off the fan"),
            # Should not strip if no wake word
            ("what time is it", "what time is it"),
            ("turn on the light", "turn on the light"),
        ],
    )
    def test_wake_word_stripping(self, input_text: str, expected: str):
        """Should strip wake words correctly."""
        result = WAKE_WORD_PATTERN.sub("", input_text).strip()
        assert result == expected

    def test_wake_word_case_insensitive(self):
        """Should handle case variations."""
        assert WAKE_WORD_PATTERN.sub("", "BARNABEE what time").strip() == "what time"
        assert WAKE_WORD_PATTERN.sub("", "BarnaBee what time").strip() == "what time"
