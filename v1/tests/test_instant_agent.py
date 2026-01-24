"""Tests for InstantAgent - zero-latency pattern-matched responses."""

from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import patch

import pytest

from barnabeenet.agents.instant import InstantAgent


@pytest.fixture
def instant_agent() -> InstantAgent:
    """Create an InstantAgent for testing."""
    return InstantAgent()


@pytest.fixture
async def initialized_agent(instant_agent: InstantAgent) -> InstantAgent:
    """Create an initialized InstantAgent."""
    await instant_agent.init()
    return instant_agent


# =============================================================================
# Time Response Tests
# =============================================================================


class TestTimeResponses:
    """Test time query handling."""

    @pytest.mark.asyncio
    async def test_time_query_returns_time(self, initialized_agent: InstantAgent) -> None:
        """Time query should return current time."""
        result = await initialized_agent.handle_input("what time is it")
        assert result["response_type"] == "time"
        assert result["agent"] == "instant"
        # Check time format (e.g., "It's 3:45 PM.")
        assert any(word in result["response"].lower() for word in ["it's", "time is", "right now"])

    @pytest.mark.asyncio
    async def test_time_query_with_sub_category(self, initialized_agent: InstantAgent) -> None:
        """Time query should work with sub_category hint."""
        result = await initialized_agent.handle_input(
            "tell me the time", context={"sub_category": "time"}
        )
        assert result["response_type"] == "time"

    @pytest.mark.asyncio
    async def test_clock_query(self, initialized_agent: InstantAgent) -> None:
        """Clock query should return time."""
        result = await initialized_agent.handle_input("what does the clock say")
        assert result["response_type"] == "time"

    @pytest.mark.asyncio
    async def test_time_response_contains_valid_time(self, initialized_agent: InstantAgent) -> None:
        """Time response should contain valid time format."""
        result = await initialized_agent.handle_input("what time is it")
        # Should contain time like "3:45 PM" or "12:00 AM"
        time_pattern = r"\d{1,2}:\d{2}\s*[AP]M"
        assert re.search(time_pattern, result["response"], re.IGNORECASE)


# =============================================================================
# Date Response Tests
# =============================================================================


class TestDateResponses:
    """Test date query handling."""

    @pytest.mark.asyncio
    async def test_date_query_returns_date(self, initialized_agent: InstantAgent) -> None:
        """Date query should return current date."""
        result = await initialized_agent.handle_input("what's the date")
        assert result["response_type"] == "date"
        assert result["agent"] == "instant"

    @pytest.mark.asyncio
    async def test_today_query(self, initialized_agent: InstantAgent) -> None:
        """Today query should return date."""
        result = await initialized_agent.handle_input("what day is today")
        assert result["response_type"] == "date"

    @pytest.mark.asyncio
    async def test_date_response_contains_valid_date(self, initialized_agent: InstantAgent) -> None:
        """Date response should contain valid date format."""
        result = await initialized_agent.handle_input("what's the date")
        # Should contain day name and month
        today = datetime.now()
        assert today.strftime("%A") in result["response"]  # Day name
        assert today.strftime("%B") in result["response"]  # Month name


# =============================================================================
# Greeting Response Tests
# =============================================================================


class TestGreetingResponses:
    """Test greeting handling."""

    @pytest.mark.asyncio
    async def test_hello_greeting(self, initialized_agent: InstantAgent) -> None:
        """Hello should return greeting."""
        result = await initialized_agent.handle_input("hello")
        assert result["response_type"] == "greeting"
        # Greeting should contain helpful phrasing
        helpful_words = ["help", "can i", "do for you", "assist", "need"]
        assert any(word in result["response"].lower() for word in helpful_words)

    @pytest.mark.asyncio
    async def test_hey_greeting(self, initialized_agent: InstantAgent) -> None:
        """Hey should return greeting."""
        result = await initialized_agent.handle_input("hey")
        assert result["response_type"] == "greeting"

    @pytest.mark.asyncio
    async def test_hi_greeting(self, initialized_agent: InstantAgent) -> None:
        """Hi should return greeting."""
        result = await initialized_agent.handle_input("hi")
        assert result["response_type"] == "greeting"

    @pytest.mark.asyncio
    async def test_good_morning_greeting(self, initialized_agent: InstantAgent) -> None:
        """Good morning should return morning greeting."""
        result = await initialized_agent.handle_input("good morning")
        assert result["response_type"] == "greeting"
        assert "morning" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_good_afternoon_greeting(self, initialized_agent: InstantAgent) -> None:
        """Good afternoon should return afternoon greeting."""
        result = await initialized_agent.handle_input("good afternoon")
        assert result["response_type"] == "greeting"
        assert "afternoon" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_good_evening_greeting(self, initialized_agent: InstantAgent) -> None:
        """Good evening should return evening greeting."""
        result = await initialized_agent.handle_input("good evening")
        assert result["response_type"] == "greeting"
        assert "evening" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_good_night_greeting(self, initialized_agent: InstantAgent) -> None:
        """Good night should return night greeting."""
        result = await initialized_agent.handle_input("good night")
        assert result["response_type"] == "greeting"
        assert "night" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_greeting_with_speaker_name(self, initialized_agent: InstantAgent) -> None:
        """Greeting should include speaker name if provided."""
        result = await initialized_agent.handle_input("hello", context={"speaker": "thom"})
        assert result["response_type"] == "greeting"
        assert "Thom" in result["response"]

    @pytest.mark.asyncio
    async def test_greeting_no_name_for_guest(self, initialized_agent: InstantAgent) -> None:
        """Greeting should not include 'guest' as name."""
        result = await initialized_agent.handle_input("hello", context={"speaker": "guest"})
        assert "guest" not in result["response"].lower()

    @pytest.mark.asyncio
    async def test_greeting_time_of_day_contextual(self, initialized_agent: InstantAgent) -> None:
        """Generic greeting should use appropriate time-of-day greeting."""
        # Mock datetime to test morning
        with patch("barnabeenet.agents.instant.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 17, 9, 0, 0)
            result = await initialized_agent.handle_input("hi")
            # Should get morning greeting
            assert result["response_type"] == "greeting"


# =============================================================================
# Status Response Tests
# =============================================================================


class TestStatusResponses:
    """Test status query handling."""

    @pytest.mark.asyncio
    async def test_how_are_you(self, initialized_agent: InstantAgent) -> None:
        """'How are you' should return status."""
        result = await initialized_agent.handle_input("how are you")
        assert result["response_type"] == "status"

    @pytest.mark.asyncio
    async def test_you_okay(self, initialized_agent: InstantAgent) -> None:
        """'You okay' should return status."""
        result = await initialized_agent.handle_input("you okay")
        assert result["response_type"] == "status"

    @pytest.mark.asyncio
    async def test_are_you_there(self, initialized_agent: InstantAgent) -> None:
        """'Are you there' should return status."""
        result = await initialized_agent.handle_input("are you there")
        assert result["response_type"] == "status"

    @pytest.mark.asyncio
    async def test_status_response_positive(self, initialized_agent: InstantAgent) -> None:
        """Status response should be positive."""
        result = await initialized_agent.handle_input("how are you")
        positive_words = ["great", "well", "good", "smoothly", "ready", "perfectly"]
        assert any(word in result["response"].lower() for word in positive_words)


# =============================================================================
# Thanks Response Tests
# =============================================================================


class TestThanksResponses:
    """Test thanks handling."""

    @pytest.mark.asyncio
    async def test_thank_you(self, initialized_agent: InstantAgent) -> None:
        """'Thank you' should return thanks response."""
        result = await initialized_agent.handle_input("thank you")
        assert result["response_type"] == "thanks"

    @pytest.mark.asyncio
    async def test_thanks(self, initialized_agent: InstantAgent) -> None:
        """'Thanks' should return thanks response."""
        result = await initialized_agent.handle_input("thanks")
        assert result["response_type"] == "thanks"

    @pytest.mark.asyncio
    async def test_thanks_response_positive(self, initialized_agent: InstantAgent) -> None:
        """Thanks response should be welcoming."""
        result = await initialized_agent.handle_input("thanks")
        positive_words = ["welcome", "happy", "anytime", "pleasure", "glad"]
        assert any(word in result["response"].lower() for word in positive_words)


# =============================================================================
# Math Response Tests
# =============================================================================


class TestMathResponses:
    """Test math expression handling."""

    @pytest.mark.asyncio
    async def test_addition(self, initialized_agent: InstantAgent) -> None:
        """Addition should work."""
        result = await initialized_agent.handle_input("what's 5 + 3")
        assert result["response_type"] == "math"
        assert "8" in result["response"]

    @pytest.mark.asyncio
    async def test_subtraction(self, initialized_agent: InstantAgent) -> None:
        """Subtraction should work."""
        result = await initialized_agent.handle_input("10 - 4")
        assert result["response_type"] == "math"
        assert "6" in result["response"]

    @pytest.mark.asyncio
    async def test_multiplication(self, initialized_agent: InstantAgent) -> None:
        """Multiplication should work."""
        result = await initialized_agent.handle_input("what is 7 * 8")
        assert result["response_type"] == "math"
        assert "56" in result["response"]

    @pytest.mark.asyncio
    async def test_division(self, initialized_agent: InstantAgent) -> None:
        """Division should work."""
        result = await initialized_agent.handle_input("15 / 3")
        assert result["response_type"] == "math"
        assert "5" in result["response"]

    @pytest.mark.asyncio
    async def test_division_by_zero(self, initialized_agent: InstantAgent) -> None:
        """Division by zero should be handled gracefully."""
        result = await initialized_agent.handle_input("10 / 0")
        assert result["response_type"] == "math"
        assert "undefined" in result["response"].lower() or "zero" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_decimal_math(self, initialized_agent: InstantAgent) -> None:
        """Decimal math should work."""
        result = await initialized_agent.handle_input("3.5 + 2.5")
        assert result["response_type"] == "math"
        assert "6" in result["response"]

    @pytest.mark.asyncio
    async def test_math_with_sub_category(self, initialized_agent: InstantAgent) -> None:
        """Math should work with sub_category hint."""
        result = await initialized_agent.handle_input(
            "calculate 100 + 50", context={"sub_category": "math"}
        )
        assert result["response_type"] == "math"
        assert "150" in result["response"]


# =============================================================================
# Fallback Response Tests
# =============================================================================


class TestFallbackResponses:
    """Test fallback handling."""

    @pytest.mark.asyncio
    async def test_unknown_query_returns_fallback(self, initialized_agent: InstantAgent) -> None:
        """Unknown queries should return fallback."""
        result = await initialized_agent.handle_input("explain quantum mechanics")
        assert result["response_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_random_text_returns_fallback(self, initialized_agent: InstantAgent) -> None:
        """Random text should return fallback."""
        result = await initialized_agent.handle_input("asdfghjkl")
        assert result["response_type"] == "fallback"


# =============================================================================
# Response Structure Tests
# =============================================================================


class TestResponseStructure:
    """Test response dictionary structure."""

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(self, initialized_agent: InstantAgent) -> None:
        """Response should contain all required fields."""
        result = await initialized_agent.handle_input("hello")
        assert "response" in result
        assert "agent" in result
        assert "response_type" in result
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_agent_name_is_instant(self, initialized_agent: InstantAgent) -> None:
        """Agent name should be 'instant'."""
        result = await initialized_agent.handle_input("hello")
        assert result["agent"] == "instant"

    @pytest.mark.asyncio
    async def test_latency_is_low(self, initialized_agent: InstantAgent) -> None:
        """Latency should be very low (< 10ms)."""
        result = await initialized_agent.handle_input("what time is it")
        assert result["latency_ms"] < 10  # Should be sub-millisecond typically


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_input(self, initialized_agent: InstantAgent) -> None:
        """Empty input should not crash."""
        result = await initialized_agent.handle_input("")
        assert result["response_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_whitespace_input(self, initialized_agent: InstantAgent) -> None:
        """Whitespace input should not crash."""
        result = await initialized_agent.handle_input("   ")
        assert result is not None

    @pytest.mark.asyncio
    async def test_none_context(self, initialized_agent: InstantAgent) -> None:
        """None context should work."""
        result = await initialized_agent.handle_input("hello", context=None)
        assert result["response_type"] == "greeting"

    @pytest.mark.asyncio
    async def test_empty_context(self, initialized_agent: InstantAgent) -> None:
        """Empty context should work."""
        result = await initialized_agent.handle_input("hello", context={})
        assert result["response_type"] == "greeting"

    @pytest.mark.asyncio
    async def test_unicode_input(self, initialized_agent: InstantAgent) -> None:
        """Unicode input should not crash."""
        result = await initialized_agent.handle_input("こんにちは")
        assert result is not None

    @pytest.mark.asyncio
    async def test_special_characters(self, initialized_agent: InstantAgent) -> None:
        """Special characters should not crash."""
        result = await initialized_agent.handle_input("!@#$%")
        assert result is not None


# =============================================================================
# Initialization/Shutdown Tests
# =============================================================================


class TestLifecycle:
    """Test agent lifecycle methods."""

    @pytest.mark.asyncio
    async def test_init_sets_math_pattern(self, instant_agent: InstantAgent) -> None:
        """Init should compile math pattern."""
        assert instant_agent._math_pattern is None
        await instant_agent.init()
        assert instant_agent._math_pattern is not None

    @pytest.mark.asyncio
    async def test_shutdown_clears_pattern(self, initialized_agent: InstantAgent) -> None:
        """Shutdown should clear math pattern."""
        assert initialized_agent._math_pattern is not None
        await initialized_agent.shutdown()
        assert initialized_agent._math_pattern is None

    @pytest.mark.asyncio
    async def test_reinitialize_after_shutdown(self, initialized_agent: InstantAgent) -> None:
        """Agent should be able to reinitialize after shutdown."""
        await initialized_agent.shutdown()
        await initialized_agent.init()
        result = await initialized_agent.handle_input("5 + 5")
        assert result["response_type"] == "math"
        assert "10" in result["response"]

    @pytest.mark.asyncio
    async def test_math_without_init(self, instant_agent: InstantAgent) -> None:
        """Math should fail gracefully without init."""
        result = await instant_agent.handle_input("5 + 5")
        # Without init, math pattern is None, so it falls back
        assert result["response_type"] == "fallback"
