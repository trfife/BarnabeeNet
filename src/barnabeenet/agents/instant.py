"""Instant Response Agent - Zero-latency pattern-matched responses.

The Instant Agent handles simple, predictable queries that don't require
LLM processing. This provides sub-millisecond response times for common
interactions like time, date, greetings, and simple math.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from barnabeenet.agents.base import Agent

logger = logging.getLogger(__name__)


@dataclass
class SpellingSession:
    """Tracks an active letter-by-letter spelling session."""

    word: str
    letters: list[str] = field(default_factory=list)
    current_index: int = 0
    awaiting_confirmation: bool = True  # Waiting for user to say "yes"

    def __post_init__(self) -> None:
        self.letters = [letter.upper() for letter in self.word]

    def get_next_letter(self) -> str | None:
        """Get the next letter, or None if done."""
        if self.current_index < len(self.letters):
            letter = self.letters[self.current_index]
            self.current_index += 1
            return letter
        return None

    def is_complete(self) -> bool:
        """Check if all letters have been given."""
        return self.current_index >= len(self.letters)

    def remaining_count(self) -> int:
        """How many letters are left."""
        return len(self.letters) - self.current_index


class InstantAgent(Agent):
    """Agent for instant, pattern-matched responses with no LLM latency.

    Handles:
    - Time queries ("what time is it")
    - Date queries ("what's the date")
    - Greetings ("hello", "good morning")
    - Status queries ("how are you")
    - Simple math ("what's 5 + 3")
    - Thanks responses
    - Spelling with optional letter-by-letter mode
    """

    name = "instant"

    # Patterns that indicate user wants to continue letter-by-letter spelling
    SPELLING_CONTINUE_PATTERNS = [
        "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "go ahead",
        "next", "continue", "go on", "keep going", "next letter",
        "and", "then", "what's next", "more", "another",
    ]

    # Patterns that indicate user wants to stop/cancel
    SPELLING_STOP_PATTERNS = [
        "no", "nope", "stop", "cancel", "nevermind", "never mind",
        "that's enough", "i got it", "thanks", "thank you", "done",
    ]

    # Response templates for variety
    TIME_RESPONSES = [
        "It's {time}.",
        "The time is {time}.",
        "Right now it's {time}.",
    ]

    DATE_RESPONSES = [
        "Today is {date}.",
        "It's {date}.",
        "The date is {date}.",
    ]

    GREETING_RESPONSES = {
        "morning": [
            "Good morning{name}! How can I help you today?",
            "Morning{name}! What can I do for you?",
            "Good morning{name}! Ready to help.",
        ],
        "afternoon": [
            "Good afternoon{name}! How can I help?",
            "Good afternoon{name}! What can I do for you?",
            "Afternoon{name}! How may I assist?",
        ],
        "evening": [
            "Good evening{name}! What can I do for you?",
            "Evening{name}! How can I help?",
            "Good evening{name}! How may I assist?",
        ],
        "night": [
            "Good night{name}! Anything I can help with before bed?",
            "Night{name}! Need anything?",
        ],
        "default": [
            "Hello{name}! How can I help you?",
            "Hey{name}! What do you need?",
            "Hi{name}! What can I do for you?",
        ],
    }

    STATUS_RESPONSES = [
        "I'm doing great, thanks for asking!",
        "All systems are running smoothly.",
        "I'm here and ready to help!",
        "Doing well! How about you?",
        "Everything's working perfectly.",
    ]

    THANKS_RESPONSES = [
        "You're welcome!",
        "Happy to help!",
        "Anytime!",
        "My pleasure!",
        "Glad I could help!",
    ]

    MIC_CHECK_RESPONSES = [
        "Yes, I can hear you loud and clear!",
        "I hear you! What can I help with?",
        "Yep, I'm here and listening!",
        "Loud and clear! Go ahead.",
        "I hear you perfectly!",
    ]

    # Clear conversation / Start fresh responses
    CLEAR_CONVERSATION_RESPONSES = [
        "Sure, starting fresh! How can I help you?",
        "Okay, I've cleared our conversation. What would you like to talk about?",
        "Fresh start! What can I do for you?",
        "Done! I've forgotten what we were discussing. What's on your mind?",
    ]

    # Patterns that indicate user wants to clear/reset conversation
    CLEAR_CONVERSATION_PATTERNS = [
        r"start\s*fresh",
        r"forget\s*this\s*conversation",
        r"clear\s*(?:the\s*)?conversation",
        r"new\s*conversation",
        r"reset\s*(?:our\s*)?(?:conversation|chat)",
        r"let'?s?\s*start\s*over",
        r"forget\s*what\s*(?:we(?:'ve)?\s*)?(?:talked|discussed|said)",
        r"wipe\s*(?:the\s*)?slate\s*clean",
    ]

    SPELLING_RESPONSES = [
        "{word} is spelled {spelling}. Would you like that one letter at a time?",
    ]

    FALLBACK_RESPONSES = [
        "I'm not sure how to respond to that.",
        "Let me think about that for a moment...",
        "Hmm, I'll need to process that.",
    ]

    def __init__(self) -> None:
        """Initialize the Instant Agent."""
        self._math_pattern: re.Pattern[str] | None = None
        self._spelling_pattern: re.Pattern[str] | None = None
        # Track active spelling sessions by speaker (or "default" if no speaker)
        self._spelling_sessions: dict[str, SpellingSession] = {}

    async def init(self) -> None:
        """Initialize patterns and resources."""
        # Compile math pattern
        self._math_pattern = re.compile(
            r"(?:what(?:'s| is) )?(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)",
            re.IGNORECASE,
        )
        # Compile spelling pattern - matches "spell X", "how do you spell X", "what's the spelling of X"
        self._spelling_pattern = re.compile(
            r"(?:how (?:do (?:you |i )?)?(?:spell|write)|"
            r"(?:can you |please )?spell(?: me)?|"
            r"what(?:'s| is) the spelling of|"
            r"spell out)\s+(?:the word\s+)?[\"']?(\w+)[\"']?\??$",
            re.IGNORECASE,
        )
        logger.info("InstantAgent initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._math_pattern = None
        self._spelling_pattern = None

    async def handle_input(self, text: str, context: dict | None = None) -> dict[str, Any]:
        """Handle an instant response request.

        Args:
            text: The input text to process
            context: Optional context with speaker info, sub_category, etc.

        Returns:
            Response dictionary with text, agent, and latency_ms
        """
        start_time = time.perf_counter()
        context = context or {}
        text = text.strip()
        text_lower = text.lower()

        # Get sub_category hint from MetaAgent if available
        sub_category = context.get("sub_category")
        speaker = context.get("speaker") or "default"

        # Determine response based on category or content
        response: str
        response_type: str

        # First, check for clear conversation commands
        if sub_category == "clear_conversation" or self._is_clear_conversation(text_lower):
            response = await self._handle_clear_conversation(context)
            response_type = "clear_conversation"
        # Check if this is a continuation of a letter-by-letter spelling session
        # This handles "yes", "next", etc. when there's an active spelling session
        elif (spelling_continuation := self._handle_spelling_continuation(text_lower, speaker)):
            response = spelling_continuation
            response_type = "spelling_letter"
        elif sub_category == "spelling_continue":
            # MetaAgent routed this as a potential spelling continuation, but no active session
            # Give a helpful response instead of a confusing one
            response = "I'm here! What would you like me to help with?"
            response_type = "acknowledgment"
        elif sub_category == "time" or self._is_time_query(text_lower):
            response = self._handle_time()
            response_type = "time"
        elif sub_category == "date" or self._is_date_query(text_lower):
            response = self._handle_date()
            response_type = "date"
        elif sub_category == "greeting" or self._is_greeting(text_lower):
            response = self._handle_greeting(text_lower, speaker)
            response_type = "greeting"
        elif sub_category == "status" or self._is_status_query(text_lower):
            response = self._handle_status()
            response_type = "status"
        elif sub_category == "thanks" or self._is_thanks(text_lower):
            response = self._handle_thanks()
            response_type = "thanks"
        elif sub_category == "mic_check" or self._is_mic_check(text_lower):
            response = self._handle_mic_check()
            response_type = "mic_check"
        elif sub_category == "spelling" or (spelling_result := self._try_spelling(text, speaker)):
            if sub_category == "spelling":
                spelling_result = self._try_spelling(text, speaker)
            if spelling_result:
                response = spelling_result
                response_type = "spelling"
            else:
                response = random.choice(self.FALLBACK_RESPONSES)
                response_type = "fallback"
        elif sub_category == "math" or (math_result := self._try_math(text)):
            if sub_category == "math":
                math_result = self._try_math(text)
            if math_result:
                response = math_result
                response_type = "math"
            else:
                response = random.choice(self.FALLBACK_RESPONSES)
                response_type = "fallback"
        else:
            response = random.choice(self.FALLBACK_RESPONSES)
            response_type = "fallback"

        latency_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "InstantAgent handled '%s' as %s in %.2fms",
            text[:50],
            response_type,
            latency_ms,
        )

        return {
            "response": response,
            "agent": self.name,
            "response_type": response_type,
            "latency_ms": latency_ms,
        }

    # =========================================================================
    # Query Detection Methods
    # =========================================================================

    def _is_time_query(self, text: str) -> bool:
        """Check if query is about time."""
        time_keywords = ["time", "what time", "clock", "o'clock"]
        return any(kw in text for kw in time_keywords)

    def _is_date_query(self, text: str) -> bool:
        """Check if query is about date."""
        date_keywords = ["date", "what day", "today", "what's today"]
        return any(kw in text for kw in date_keywords)

    def _is_greeting(self, text: str) -> bool:
        """Check if text is a greeting."""
        greetings = [
            "hello",
            "hey",
            "hi",
            "good morning",
            "good afternoon",
            "good evening",
            "good night",
        ]
        return any(text.startswith(g) or text == g for g in greetings)

    def _is_status_query(self, text: str) -> bool:
        """Check if asking about status."""
        status_keywords = ["how are you", "you okay", "are you there", "you alright"]
        return any(kw in text for kw in status_keywords)

    def _is_thanks(self, text: str) -> bool:
        """Check if expressing thanks."""
        thanks_keywords = ["thank", "thanks", "cheers", "appreciate"]
        return any(kw in text for kw in thanks_keywords)

    def _is_mic_check(self, text: str) -> bool:
        """Check if this is a mic test or hearing check."""
        mic_keywords = [
            "can you hear me",
            "do you hear me",
            "are you there",
            "testing",
            "test",
            "is this working",
            "am i working",
        ]
        return any(kw in text for kw in mic_keywords)

    # =========================================================================
    # Response Handlers
    # =========================================================================

    def _handle_time(self) -> str:
        """Generate time response."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")  # Remove leading zero
        template = random.choice(self.TIME_RESPONSES)
        return template.format(time=time_str)

    def _handle_date(self) -> str:
        """Generate date response."""
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        template = random.choice(self.DATE_RESPONSES)
        return template.format(date=date_str)

    def _handle_greeting(self, text: str, speaker: str | None) -> str:
        """Generate contextual greeting based on time of day."""
        now = datetime.now()
        hour = now.hour

        # Check for explicit time-of-day greeting
        if "morning" in text:
            time_key = "morning"
        elif "afternoon" in text:
            time_key = "afternoon"
        elif "evening" in text:
            time_key = "evening"
        elif "night" in text:
            time_key = "night"
        # Otherwise determine from current time
        elif 5 <= hour < 12:
            time_key = "morning"
        elif 12 <= hour < 17:
            time_key = "afternoon"
        elif 17 <= hour < 22:
            time_key = "evening"
        else:
            time_key = "default"

        template = random.choice(self.GREETING_RESPONSES[time_key])

        # Personalize if speaker known
        name_str = ""
        if speaker and speaker.lower() not in ("guest", "unknown"):
            name_str = f", {speaker.title()}"

        return template.format(name=name_str)

    def _handle_status(self) -> str:
        """Generate status response."""
        return random.choice(self.STATUS_RESPONSES)

    def _handle_thanks(self) -> str:
        """Generate thanks response."""
        return random.choice(self.THANKS_RESPONSES)

    def _handle_mic_check(self) -> str:
        """Generate mic check / hearing confirmation response."""
        return random.choice(self.MIC_CHECK_RESPONSES)

    def _is_clear_conversation(self, text: str) -> bool:
        """Check if user wants to clear/reset the conversation."""
        for pattern in self.CLEAR_CONVERSATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    async def _handle_clear_conversation(self, context: dict[str, Any]) -> str:
        """Handle clear conversation request.

        Clears the conversation context for the current device/room.
        """
        conversation_id = context.get("conversation_id")

        if conversation_id:
            try:
                # Try to get the interaction agent and clear the conversation
                from barnabeenet.main import app_state
                if hasattr(app_state, "orchestrator") and app_state.orchestrator:
                    orchestrator = app_state.orchestrator
                    if hasattr(orchestrator, "_interaction_agent") and orchestrator._interaction_agent:
                        await orchestrator._interaction_agent.clear_conversation(conversation_id)
                        logger.info(f"Cleared conversation: {conversation_id}")
            except Exception as e:
                logger.warning(f"Failed to clear conversation {conversation_id}: {e}")

        return random.choice(self.CLEAR_CONVERSATION_RESPONSES)

    def _try_math(self, text: str) -> str | None:
        """Try to evaluate simple math expressions.

        Supports: +, -, *, /
        Examples: "what's 5 + 3", "5 * 7", "10 / 2"
        """
        if self._math_pattern is None:
            return None

        match = self._math_pattern.search(text)
        if not match:
            return None

        try:
            a = float(match.group(1))
            op = match.group(2)
            b = float(match.group(3))

            operations = {
                "+": lambda x, y: x + y,
                "-": lambda x, y: x - y,
                "*": lambda x, y: x * y,
                "/": lambda x, y: x / y if y != 0 else None,
            }

            result = operations[op](a, b)

            if result is None:
                return "That's undefined - you can't divide by zero!"

            # Format nicely
            if result == int(result):
                result_str = str(int(result))
            else:
                result_str = f"{result:.2f}".rstrip("0").rstrip(".")

            return f"That's {result_str}."

        except (ValueError, KeyError, ZeroDivisionError):
            return None

    def _handle_spelling_continuation(self, text_lower: str, speaker: str) -> str | None:
        """Handle continuation of a letter-by-letter spelling session.

        Returns response if this is a continuation, None otherwise.
        """
        session = self._spelling_sessions.get(speaker)
        if not session:
            return None

        # Check if user wants to stop
        if any(pattern in text_lower for pattern in self.SPELLING_STOP_PATTERNS):
            del self._spelling_sessions[speaker]
            return "Okay, no problem!"

        # Check if user wants to continue (or is confirming to start)
        is_continue = any(pattern in text_lower for pattern in self.SPELLING_CONTINUE_PATTERNS)

        if session.awaiting_confirmation:
            if is_continue:
                # User said yes - start giving letters
                session.awaiting_confirmation = False
                letter = session.get_next_letter()
                if letter:
                    if session.is_complete():
                        # Only one letter word, we're done
                        del self._spelling_sessions[speaker]
                        return f"{letter}. That's the whole word!"
                    return letter
            else:
                # User said something else - assume they don't want letter-by-letter
                del self._spelling_sessions[speaker]
                return None

        # User is asking for next letter
        if is_continue:
            letter = session.get_next_letter()
            if letter:
                if session.is_complete():
                    # Last letter
                    del self._spelling_sessions[speaker]
                    return f"{letter}. That's the last letter!"
                return letter
            else:
                # No more letters
                del self._spelling_sessions[speaker]
                return "That's all the letters!"

        # User said something that doesn't match - end the session
        del self._spelling_sessions[speaker]
        return None

    def _try_spelling(self, text: str, speaker: str = "default") -> str | None:
        """Try to spell a word from the input.

        Supports: "spell dinosaur", "how do you spell beautiful", etc.
        Returns the word spelled out letter by letter with offer for slow mode.
        """
        if self._spelling_pattern is None:
            return None

        match = self._spelling_pattern.search(text)
        if not match:
            return None

        word = match.group(1).strip()
        if not word:
            return None

        # Spell out the word with spaces between letters
        spelling = " ".join(letter.upper() for letter in word)

        # Create a spelling session for potential letter-by-letter follow-up
        self._spelling_sessions[speaker] = SpellingSession(word=word)

        template = random.choice(self.SPELLING_RESPONSES)
        return template.format(word=word.lower(), spelling=spelling)


__all__ = ["InstantAgent"]
