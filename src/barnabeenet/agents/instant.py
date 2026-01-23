"""Instant Response Agent - Zero-latency pattern-matched responses.

The Instant Agent handles simple, predictable queries that don't require
LLM processing. This provides sub-millisecond response times for common
interactions like time, date, greetings, and simple math.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from barnabeenet.agents.base import Agent

logger = logging.getLogger(__name__)

# Load jokes and fun facts from data files
DATA_DIR = Path(__file__).parent.parent / "data"

def _load_json_data(filename: str) -> dict:
    """Load JSON data from the data directory."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {filename}: {e}")
    return {}

JOKES_DATA = _load_json_data("jokes.json")
FUN_FACTS_DATA = _load_json_data("fun_facts.json")
ANIMAL_SOUNDS_DATA = _load_json_data("animal_sounds.json")
TRIVIA_DATA = _load_json_data("trivia.json")
WOULD_YOU_RATHER_DATA = _load_json_data("would_you_rather.json")
ENCOURAGEMENT_DATA = _load_json_data("encouragement.json")


# =============================================================================
# Unit Conversion Data
# =============================================================================
UNIT_CONVERSIONS = {
    # Volume
    ("cups", "liters"): (0.236588, "liters"),
    ("cups", "liter"): (0.236588, "liters"),
    ("liters", "cups"): (4.22675, "cups"),
    ("liter", "cups"): (4.22675, "cups"),
    ("gallons", "liters"): (3.78541, "liters"),
    ("gallon", "liters"): (3.78541, "liters"),
    ("liters", "gallons"): (0.264172, "gallons"),
    ("liter", "gallons"): (0.264172, "gallons"),
    ("tablespoons", "teaspoons"): (3, "teaspoons"),
    ("tablespoon", "teaspoons"): (3, "teaspoons"),
    ("teaspoons", "tablespoons"): (1/3, "tablespoons"),
    ("teaspoon", "tablespoons"): (1/3, "tablespoons"),
    ("cups", "tablespoons"): (16, "tablespoons"),
    ("cup", "tablespoons"): (16, "tablespoons"),
    ("tablespoons", "cups"): (1/16, "cups"),
    ("tablespoon", "cups"): (1/16, "cups"),
    ("ounces", "cups"): (0.125, "cups"),
    ("ounce", "cups"): (0.125, "cups"),
    ("cups", "ounces"): (8, "ounces"),
    ("cup", "ounces"): (8, "ounces"),
    # Temperature (handled specially)
    # Weight
    ("pounds", "kilograms"): (0.453592, "kilograms"),
    ("pound", "kilograms"): (0.453592, "kilograms"),
    ("kilograms", "pounds"): (2.20462, "pounds"),
    ("kilogram", "pounds"): (2.20462, "pounds"),
    ("ounces", "grams"): (28.3495, "grams"),
    ("ounce", "grams"): (28.3495, "grams"),
    ("grams", "ounces"): (0.035274, "ounces"),
    ("gram", "ounces"): (0.035274, "ounces"),
    ("ounces", "pounds"): (0.0625, "pounds"),
    ("ounce", "pounds"): (0.0625, "pounds"),
    ("pounds", "ounces"): (16, "ounces"),
    ("pound", "ounces"): (16, "ounces"),
    # Length
    ("inches", "centimeters"): (2.54, "centimeters"),
    ("inch", "centimeters"): (2.54, "centimeters"),
    ("centimeters", "inches"): (0.393701, "inches"),
    ("centimeter", "inches"): (0.393701, "inches"),
    ("feet", "meters"): (0.3048, "meters"),
    ("foot", "meters"): (0.3048, "meters"),
    ("meters", "feet"): (3.28084, "feet"),
    ("meter", "feet"): (3.28084, "feet"),
    ("miles", "kilometers"): (1.60934, "kilometers"),
    ("mile", "kilometers"): (1.60934, "kilometers"),
    ("kilometers", "miles"): (0.621371, "miles"),
    ("kilometer", "miles"): (0.621371, "miles"),
    ("feet", "inches"): (12, "inches"),
    ("foot", "inches"): (12, "inches"),
    ("inches", "feet"): (1/12, "feet"),
    ("inch", "feet"): (1/12, "feet"),
    ("yards", "feet"): (3, "feet"),
    ("yard", "feet"): (3, "feet"),
    ("feet", "yards"): (1/3, "yards"),
    ("foot", "yards"): (1/3, "yards"),
    ("miles", "feet"): (5280, "feet"),
    ("mile", "feet"): (5280, "feet"),
    ("feet", "miles"): (1/5280, "miles"),
    ("foot", "miles"): (1/5280, "miles"),
}

# Common unit info queries
UNIT_INFO = {
    ("cups", "liter"): "About 4.2 cups in a liter.",
    ("cups", "liters"): "About 4.2 cups in a liter.",
    ("ounces", "pound"): "16 ounces in a pound.",
    ("ounces", "pounds"): "16 ounces in a pound.",
    ("inches", "foot"): "12 inches in a foot.",
    ("inches", "feet"): "12 inches in a foot.",
    ("feet", "mile"): "5,280 feet in a mile.",
    ("feet", "miles"): "5,280 feet in a mile.",
    ("teaspoons", "tablespoon"): "3 teaspoons in a tablespoon.",
    ("teaspoons", "tablespoons"): "3 teaspoons in a tablespoon.",
    ("tablespoons", "cup"): "16 tablespoons in a cup.",
    ("tablespoons", "cups"): "16 tablespoons in a cup.",
    ("centimeters", "inch"): "2.54 centimeters in an inch.",
    ("centimeters", "inches"): "2.54 centimeters in an inch.",
    ("grams", "ounce"): "About 28.3 grams in an ounce.",
    ("grams", "ounces"): "About 28.3 grams in an ounce.",
}

# World clock timezone mappings
TIMEZONE_ALIASES = {
    # Major cities
    "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo",
    "london": "Europe/London",
    "uk": "Europe/London",
    "england": "Europe/London",
    "britain": "Europe/London",
    "paris": "Europe/Paris",
    "france": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "germany": "Europe/Berlin",
    "sydney": "Australia/Sydney",
    "australia": "Australia/Sydney",
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "denver": "America/Denver",
    "phoenix": "America/Phoenix",
    "seattle": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "sf": "America/Los_Angeles",
    "miami": "America/New_York",
    "boston": "America/New_York",
    "dallas": "America/Chicago",
    "houston": "America/Chicago",
    "atlanta": "America/New_York",
    "toronto": "America/Toronto",
    "canada": "America/Toronto",
    "vancouver": "America/Vancouver",
    "mexico city": "America/Mexico_City",
    "mexico": "America/Mexico_City",
    "beijing": "Asia/Shanghai",
    "china": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong",
    "singapore": "Asia/Singapore",
    "seoul": "Asia/Seoul",
    "korea": "Asia/Seoul",
    "south korea": "Asia/Seoul",
    "mumbai": "Asia/Kolkata",
    "india": "Asia/Kolkata",
    "dubai": "Asia/Dubai",
    "uae": "Asia/Dubai",
    "moscow": "Europe/Moscow",
    "russia": "Europe/Moscow",
    "amsterdam": "Europe/Amsterdam",
    "netherlands": "Europe/Amsterdam",
    "rome": "Europe/Rome",
    "italy": "Europe/Rome",
    "madrid": "Europe/Madrid",
    "spain": "Europe/Madrid",
    "lisbon": "Europe/Lisbon",
    "portugal": "Europe/Lisbon",
    "cairo": "Africa/Cairo",
    "egypt": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg",
    "south africa": "Africa/Johannesburg",
    "hawaii": "Pacific/Honolulu",
    "honolulu": "Pacific/Honolulu",
    "alaska": "America/Anchorage",
    # Time zones by abbreviation
    "est": "America/New_York",
    "eastern": "America/New_York",
    "cst": "America/Chicago",
    "central": "America/Chicago",
    "mst": "America/Denver",
    "mountain": "America/Denver",
    "pst": "America/Los_Angeles",
    "pacific": "America/Los_Angeles",
    "gmt": "Europe/London",
    "utc": "UTC",
}

# Magic 8-ball responses
MAGIC_8_BALL_RESPONSES = [
    # Positive
    "It is certain.",
    "It is decidedly so.",
    "Without a doubt.",
    "Yes, definitely.",
    "You may rely on it.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Yes.",
    "Signs point to yes.",
    # Neutral
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    # Negative
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful.",
]

# Holiday dates (month, day) - updated annually or calculated
HOLIDAYS = {
    "christmas": (12, 25),
    "christmas eve": (12, 24),
    "new year": (1, 1),
    "new years": (1, 1),
    "new year's": (1, 1),
    "new year's day": (1, 1),
    "new year's eve": (12, 31),
    "valentine's day": (2, 14),
    "valentines day": (2, 14),
    "st patrick's day": (3, 17),
    "st patricks day": (3, 17),
    "easter": None,  # Calculated
    "mother's day": None,  # 2nd Sunday in May
    "mothers day": None,
    "father's day": None,  # 3rd Sunday in June
    "fathers day": None,
    "independence day": (7, 4),
    "fourth of july": (7, 4),
    "4th of july": (7, 4),
    "halloween": (10, 31),
    "thanksgiving": None,  # 4th Thursday in November
    "summer": (6, 21),  # Summer solstice
    "winter": (12, 21),  # Winter solstice
    "spring": (3, 20),  # Spring equinox
    "fall": (9, 22),  # Fall equinox
    "autumn": (9, 22),
}


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

    UNDO_RESPONSES = [
        "Done! I've undone the last action.",
        "Okay, I've reversed that.",
        "No problem, I've undone it.",
    ]

    NOTHING_TO_UNDO_RESPONSES = [
        "There's nothing to undo.",
        "I don't have any recent actions to undo.",
        "Hmm, I haven't done anything I can undo.",
    ]

    REPEAT_RESPONSES = [
        "I said: {last_response}",
        "Sure, I said: {last_response}",
        "Here's what I said: {last_response}",
    ]

    NOTHING_TO_REPEAT_RESPONSES = [
        "I haven't said anything yet.",
        "There's nothing to repeat.",
        "This is the start of our conversation.",
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

    # Random choice responses
    COIN_FLIP_RESPONSES = [
        "I flipped a coin and got... {result}!",
        "The coin landed on... {result}!",
        "{result}!",
    ]

    DICE_ROLL_RESPONSES = [
        "You rolled a {result}!",
        "The dice shows {result}!",
        "It's a {result}!",
    ]

    NUMBER_PICK_RESPONSES = [
        "I pick... {result}!",
        "How about {result}?",
        "My choice is {result}!",
        "I'm going with {result}!",
    ]

    YES_NO_RESPONSES = [
        "Yes!",
        "No!",
    ]

    # Counting responses
    COUNTING_RESPONSES = [
        "{numbers}, blastoff!",
        "{numbers}!",
        "Here you go: {numbers}",
    ]

    def __init__(self) -> None:
        """Initialize the Instant Agent."""
        self._math_pattern: re.Pattern[str] | None = None
        self._spelling_pattern: re.Pattern[str] | None = None
        self._dice_pattern: re.Pattern[str] | None = None
        self._number_pick_pattern: re.Pattern[str] | None = None
        self._unit_convert_pattern: re.Pattern[str] | None = None
        self._unit_info_pattern: re.Pattern[str] | None = None
        self._world_clock_pattern: re.Pattern[str] | None = None
        self._countdown_pattern: re.Pattern[str] | None = None
        self._counting_pattern: re.Pattern[str] | None = None
        self._next_number_pattern: re.Pattern[str] | None = None
        # Track active spelling sessions by speaker (or "default" if no speaker)
        self._spelling_sessions: dict[str, SpellingSession] = {}

    async def init(self) -> None:
        """Initialize patterns and resources."""
        # Compile math pattern - supports both symbols and words
        # Matches: "5 + 3", "what's 7 times 8", "10 divided by 2", "5 plus 3"
        self._math_pattern = re.compile(
            r"(?:what(?:'s| is) )?(\d+(?:\.\d+)?)\s*"
            r"([\+\-\*\/]|plus|minus|times|multiplied by|divided by|x)\s*"
            r"(\d+(?:\.\d+)?)",
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
        # Dice roll pattern - "roll a dice", "roll a d20", "roll 2d6"
        self._dice_pattern = re.compile(
            r"(?:roll|throw)\s+(?:a\s+)?(?:(?:d|dice|die)(?:(\d+))?|(\d+)d(\d+))",
            re.IGNORECASE,
        )
        # Pick number pattern - "pick a number between X and Y"
        self._number_pick_pattern = re.compile(
            r"pick\s+(?:a\s+)?(?:random\s+)?number\s+(?:between|from)\s+(\d+)\s+(?:and|to)\s+(\d+)",
            re.IGNORECASE,
        )
        # Unit conversion pattern - "convert X unit to unit" or "how many X in Y"
        self._unit_convert_pattern = re.compile(
            r"(?:convert\s+)?(\d+(?:\.\d+)?)\s*"
            r"(fahrenheit|celsius|cups?|liters?|gallons?|pounds?|kilograms?|ounces?|grams?|"
            r"inches?|centimeters?|feet|foot|meters?|miles?|kilometers?|yards?|"
            r"tablespoons?|teaspoons?)\s+"
            r"(?:to|in(?:to)?)\s+"
            r"(fahrenheit|celsius|cups?|liters?|gallons?|pounds?|kilograms?|ounces?|grams?|"
            r"inches?|centimeters?|feet|foot|meters?|miles?|kilometers?|yards?|"
            r"tablespoons?|teaspoons?)",
            re.IGNORECASE,
        )
        # "How many X in a Y" pattern
        self._unit_info_pattern = re.compile(
            r"how many\s+(cups?|liters?|ounces?|inches?|feet|foot|"
            r"centimeters?|teaspoons?|tablespoons?|grams?)\s+"
            r"(?:are\s+)?(?:there\s+)?in\s+(?:a\s+)?"
            r"(cup|liter|pound|foot|feet|mile|tablespoon|inch|ounce)",
            re.IGNORECASE,
        )
        # World clock pattern - "what time is it in Tokyo"
        self._world_clock_pattern = re.compile(
            r"(?:what(?:'s| is)?|tell me)\s+(?:the\s+)?time\s+(?:is\s+it\s+)?in\s+(.+?)(?:\?|$)",
            re.IGNORECASE,
        )
        # Countdown pattern - "how many days until Christmas"
        self._countdown_pattern = re.compile(
            r"(?:how (?:many|long)|when is|days? (?:until|till|to))\s+"
            r"(?:days?\s+)?(?:until|till|to|before)?\s*(.+?)(?:\?|$)",
            re.IGNORECASE,
        )
        # Counting pattern - "count to 10", "count by 2s to 20", "count backwards from 10"
        self._counting_pattern = re.compile(
            r"count\s+"
            r"(?:(backwards?|down)\s+)?(?:from\s+)?(\d+)?\s*"
            r"(?:to\s+(\d+))?\s*"
            r"(?:by\s+(\d+)(?:s|'s)?)?",
            re.IGNORECASE,
        )
        # "What comes after X" pattern
        self._next_number_pattern = re.compile(
            r"what(?:'s| is)?\s+(?:comes?\s+)?(?:after|next after|before)\s+(\d+)",
            re.IGNORECASE,
        )
        logger.info("InstantAgent initialized with extended patterns")

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

        # First, check for undo/repeat which need special handling
        if sub_category == "undo" or self._is_undo(text_lower):
            response = await self._handle_undo(context)
            response_type = "undo"
        elif sub_category == "repeat" or self._is_repeat(text_lower):
            response = self._handle_repeat(context)
            response_type = "repeat"
        # Check for clear conversation commands
        elif sub_category == "clear_conversation" or self._is_clear_conversation(text_lower):
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
        # Random choices
        elif sub_category == "coin_flip" or self._is_coin_flip(text_lower):
            response = self._handle_coin_flip()
            response_type = "coin_flip"
        elif sub_category == "dice_roll" or self._is_dice_roll(text_lower):
            response = self._handle_dice_roll(text)
            response_type = "dice_roll"
        elif sub_category == "yes_no" or self._is_yes_no(text_lower):
            response = self._handle_yes_no()
            response_type = "yes_no"
        elif sub_category == "magic_8_ball" or self._is_magic_8_ball(text_lower):
            response = self._handle_magic_8_ball()
            response_type = "magic_8_ball"
        elif sub_category == "number_pick" or "pick a number" in text_lower or "pick a random" in text_lower:
            response = self._handle_number_pick(text)
            response_type = "number_pick"
        # World clock
        elif sub_category == "world_clock" or self._is_world_clock(text_lower):
            result = self._handle_world_clock(text)
            if result:
                response = result
                response_type = "world_clock"
            else:
                response = random.choice(self.FALLBACK_RESPONSES)
                response_type = "fallback"
        # Countdown to events
        elif sub_category == "countdown" or self._is_countdown(text_lower):
            result = self._handle_countdown(text)
            if result:
                response = result
                response_type = "countdown"
            else:
                response = random.choice(self.FALLBACK_RESPONSES)
                response_type = "fallback"
        # Counting
        elif sub_category == "counting" or self._is_counting(text_lower):
            result = self._handle_counting(text)
            if result:
                response = result
                response_type = "counting"
            else:
                response = random.choice(self.FALLBACK_RESPONSES)
                response_type = "fallback"
        # Unit conversions
        elif sub_category == "unit_conversion" or self._is_unit_conversion(text_lower):
            result = self._handle_unit_conversion(text)
            if result:
                response = result
                response_type = "unit_conversion"
            else:
                response = random.choice(self.FALLBACK_RESPONSES)
                response_type = "fallback"
        # Jokes
        elif sub_category == "joke" or self._is_joke(text_lower):
            response = self._handle_joke(text)
            response_type = "joke"
        elif sub_category == "riddle" or self._is_riddle(text_lower):
            response = self._handle_riddle()
            response_type = "riddle"
        # Fun facts
        elif sub_category == "fun_fact" or self._is_fun_fact(text_lower):
            response = self._handle_fun_fact(text)
            response_type = "fun_fact"
        # Animal sounds
        elif sub_category == "animal_sound" or self._is_animal_sound(text_lower):
            response = self._handle_animal_sound(text)
            response_type = "animal_sound"
        # Math practice
        elif sub_category == "math_practice" or self._is_math_practice(text_lower):
            response = self._handle_math_practice(context)
            response_type = "math_practice"
        # Bedtime countdown
        elif sub_category == "bedtime" or self._is_bedtime_query(text_lower):
            response = await self._handle_bedtime_countdown(context)
            response_type = "bedtime"
        # Trivia
        elif sub_category == "trivia" or self._is_trivia(text_lower):
            response = self._handle_trivia(context)
            response_type = "trivia"
        # Would you rather
        elif sub_category == "would_you_rather" or self._is_would_you_rather(text_lower):
            response = self._handle_would_you_rather()
            response_type = "would_you_rather"
        # Encouragement / compliments
        elif sub_category == "encouragement" or self._is_encouragement(text_lower):
            response = self._handle_encouragement(text)
            response_type = "encouragement"
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
        # Avoid matching "times" (as in multiplication)
        if "times" in text and any(c.isdigit() for c in text):
            return False
        time_keywords = ["what time", "the time", "clock", "o'clock"]
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

    def _is_coin_flip(self, text: str) -> bool:
        """Check if user wants to flip a coin."""
        return any(kw in text for kw in ["flip a coin", "flip coin", "heads or tails", "coin flip"])

    def _is_dice_roll(self, text: str) -> bool:
        """Check if user wants to roll dice."""
        return any(kw in text for kw in ["roll a dice", "roll dice", "roll a die", "roll a d", "throw dice"])

    def _is_yes_no(self, text: str) -> bool:
        """Check if user wants a yes/no decision."""
        return text.strip().lower() in ["yes or no", "yes or no?"]

    def _is_magic_8_ball(self, text: str) -> bool:
        """Check if user wants magic 8-ball."""
        return any(kw in text for kw in ["magic 8 ball", "magic 8-ball", "magic eight ball", "8 ball"])

    def _is_world_clock(self, text: str) -> bool:
        """Check if asking about time in another location."""
        return self._world_clock_pattern and self._world_clock_pattern.search(text) is not None

    def _is_countdown(self, text: str) -> bool:
        """Check if asking about countdown to event."""
        countdown_keywords = ["days until", "days till", "how long until", "how many days", "when is"]
        return any(kw in text for kw in countdown_keywords)

    def _is_counting(self, text: str) -> bool:
        """Check if user wants counting help."""
        return text.startswith("count ") or "what comes after" in text or "what comes before" in text

    def _is_unit_conversion(self, text: str) -> bool:
        """Check if asking about unit conversion."""
        conversion_keywords = ["convert", "how many", "in a ", "to celsius", "to fahrenheit", "to cups", "to liters"]
        return any(kw in text for kw in conversion_keywords)

    def _is_undo(self, text: str) -> bool:
        """Check if user wants to undo last action."""
        undo_keywords = ["undo", "undo that", "reverse that", "take that back", "never mind", "nevermind"]
        return any(kw in text for kw in undo_keywords) and "conversation" not in text

    def _is_repeat(self, text: str) -> bool:
        """Check if user wants to hear last response again."""
        repeat_keywords = [
            "say that again", "repeat that", "what did you say",
            "say it again", "come again", "pardon", "repeat",
            "what was that", "i didn't hear", "one more time"
        ]
        return any(kw in text for kw in repeat_keywords)

    def _is_joke(self, text: str) -> bool:
        """Check if user wants a joke."""
        joke_keywords = ["tell me a joke", "tell a joke", "joke please", "another joke", "got a joke",
                        "dad joke", "knock knock", "make me laugh", "animal joke", "school joke"]
        return any(kw in text for kw in joke_keywords)

    def _is_riddle(self, text: str) -> bool:
        """Check if user wants a riddle."""
        riddle_keywords = ["tell me a riddle", "riddle", "give me a riddle"]
        return any(kw in text for kw in riddle_keywords)

    def _is_fun_fact(self, text: str) -> bool:
        """Check if user wants a fun fact."""
        fact_keywords = ["tell me a fact", "fun fact", "interesting fact", "tell me something", "did you know"]
        return any(kw in text for kw in fact_keywords)

    def _is_animal_sound(self, text: str) -> bool:
        """Check if user wants to know an animal sound."""
        sound_keywords = [
            "what does a", "what do", "what sound does",
            "how does a", "what noise does", "sound does a"
        ]
        animal_words = ["say", "sound", "noise", "make", "go"]
        return any(kw in text for kw in sound_keywords) and any(aw in text for aw in animal_words)

    def _is_math_practice(self, text: str) -> bool:
        """Check if user wants math practice."""
        math_keywords = [
            "math problem", "math question", "quiz me", "test me",
            "give me a math", "practice math", "math practice"
        ]
        return any(kw in text for kw in math_keywords)

    def _is_bedtime_query(self, text: str) -> bool:
        """Check if user is asking about bedtime."""
        bedtime_keywords = [
            "how long until bedtime", "when is bedtime", "bedtime countdown",
            "time until bed", "when do i go to bed", "how much longer until bed"
        ]
        return any(kw in text for kw in bedtime_keywords)

    def _is_trivia(self, text: str) -> bool:
        """Check if user wants trivia."""
        trivia_keywords = [
            "trivia", "quiz question", "ask me a question", "test my knowledge"
        ]
        return any(kw in text for kw in trivia_keywords)

    def _is_would_you_rather(self, text: str) -> bool:
        """Check if user wants a 'would you rather' question."""
        return "would you rather" in text

    def _is_encouragement(self, text: str) -> bool:
        """Check if user wants encouragement or a compliment."""
        keywords = [
            "give me a compliment", "compliment me", "say something nice",
            "i'm feeling down", "i feel sad", "cheer me up", "motivate me",
            "encourage me", "i need encouragement"
        ]
        return any(kw in text for kw in keywords)

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

    async def _handle_undo(self, context: dict[str, Any]) -> str:
        """Handle undo request by calling orchestrator."""
        conversation_id = context.get("conversation_id")

        if not conversation_id:
            return random.choice(self.NOTHING_TO_UNDO_RESPONSES)

        try:
            from barnabeenet.main import app_state
            if hasattr(app_state, "orchestrator") and app_state.orchestrator:
                result = await app_state.orchestrator.undo_last_action(conversation_id)
                if result.get("success"):
                    return random.choice(self.UNDO_RESPONSES)
                else:
                    return result.get("message", random.choice(self.NOTHING_TO_UNDO_RESPONSES))
        except Exception as e:
            logger.warning(f"Failed to undo: {e}")

        return random.choice(self.NOTHING_TO_UNDO_RESPONSES)

    def _handle_repeat(self, context: dict[str, Any]) -> str:
        """Handle repeat/say that again request."""
        conversation_id = context.get("conversation_id")

        if not conversation_id:
            return random.choice(self.NOTHING_TO_REPEAT_RESPONSES)

        try:
            from barnabeenet.main import app_state
            if hasattr(app_state, "orchestrator") and app_state.orchestrator:
                last_response = app_state.orchestrator.get_last_response(conversation_id)
                if last_response:
                    template = random.choice(self.REPEAT_RESPONSES)
                    return template.format(last_response=last_response)
        except Exception as e:
            logger.warning(f"Failed to get last response: {e}")

        return random.choice(self.NOTHING_TO_REPEAT_RESPONSES)

    def _handle_joke(self, text: str) -> str:
        """Tell a joke based on the type requested."""
        text_lower = text.lower()

        # Determine joke category
        if "dad" in text_lower:
            category = "dad_jokes"
        elif "knock" in text_lower:
            category = "knock_knock"
        elif "animal" in text_lower:
            category = "animal"
        elif "school" in text_lower:
            category = "school"
        else:
            # Pick from general or dad jokes
            category = random.choice(["general", "dad_jokes"])

        jokes = JOKES_DATA.get(category, JOKES_DATA.get("general", []))
        if not jokes:
            return "I'm sorry, I'm fresh out of jokes right now!"

        joke = random.choice(jokes)
        setup = joke.get("setup", "")
        punchline = joke.get("punchline", "")

        return f"{setup} {punchline}"

    def _handle_riddle(self) -> str:
        """Tell a riddle."""
        riddles = JOKES_DATA.get("riddles", [])
        if not riddles:
            return "I don't have any riddles right now!"

        riddle = random.choice(riddles)
        setup = riddle.get("setup", "")
        punchline = riddle.get("punchline", "")

        # For riddles, give time to think
        return f"Here's a riddle: {setup} Think about it... The answer is: {punchline}"

    def _handle_fun_fact(self, text: str) -> str:
        """Tell a fun fact based on the topic requested."""
        text_lower = text.lower()

        # Determine fact category
        if "space" in text_lower or "planet" in text_lower or "star" in text_lower:
            category = "space"
        elif "animal" in text_lower:
            category = "animals"
        elif "science" in text_lower:
            category = "science"
        elif "history" in text_lower:
            category = "history"
        elif "food" in text_lower:
            category = "food"
        elif "geography" in text_lower or "country" in text_lower or "world" in text_lower:
            category = "geography"
        else:
            category = "general"

        facts = FUN_FACTS_DATA.get(category, FUN_FACTS_DATA.get("general", []))
        if not facts:
            return "I don't have any fun facts right now!"

        fact = random.choice(facts)
        prefixes = ["Did you know? ", "Here's a fun fact: ", "Fun fact: ", ""]
        return random.choice(prefixes) + fact

    def _handle_animal_sound(self, text: str) -> str:
        """Tell what sound an animal makes."""
        text_lower = text.lower()
        animals = ANIMAL_SOUNDS_DATA.get("animals", {})
        templates = ANIMAL_SOUNDS_DATA.get("response_templates", ["{animal}s say {sound}"])

        # Find which animal is being asked about
        found_animal = None
        for animal in animals.keys():
            if animal in text_lower:
                found_animal = animal
                break

        if not found_animal:
            return "I'm not sure which animal you're asking about. Try asking about a dog, cat, cow, or another animal!"

        animal_data = animals[found_animal]
        sound = animal_data.get("sound", "makes a sound")

        template = random.choice(templates)
        return template.format(animal=found_animal.capitalize(), sound=sound)

    def _handle_math_practice(self, context: dict[str, Any]) -> str:
        """Generate a math problem appropriate for the speaker's age."""
        speaker = context.get("speaker", "").lower()

        # Determine difficulty based on speaker (family member profiles)
        # Default to medium difficulty
        difficulty = "medium"
        if speaker in ["viola", "zachary"]:  # Younger kids
            difficulty = "easy"
        elif speaker in ["penelope", "xander"]:  # Older kids
            difficulty = "medium"
        elif speaker in ["thom", "elizabeth"]:  # Adults
            difficulty = "hard"

        if difficulty == "easy":
            # Simple addition/subtraction with small numbers
            ops = ["+", "-"]
            a = random.randint(1, 10)
            b = random.randint(1, 10)
            if random.choice(ops) == "-":
                a, b = max(a, b), min(a, b)  # Ensure positive result
                op, answer = "-", a - b
            else:
                op, answer = "+", a + b
        elif difficulty == "medium":
            # Addition, subtraction, multiplication
            ops = ["+", "-", "×"]
            op = random.choice(ops)
            if op == "×":
                a = random.randint(2, 12)
                b = random.randint(2, 12)
                answer = a * b
            elif op == "-":
                a = random.randint(10, 50)
                b = random.randint(1, a)
                answer = a - b
            else:
                a = random.randint(10, 50)
                b = random.randint(10, 50)
                answer = a + b
        else:  # hard
            # Include division and larger numbers
            ops = ["+", "-", "×", "÷"]
            op = random.choice(ops)
            if op == "÷":
                answer = random.randint(2, 12)
                b = random.randint(2, 12)
                a = answer * b
            elif op == "×":
                a = random.randint(5, 20)
                b = random.randint(5, 20)
                answer = a * b
            elif op == "-":
                a = random.randint(50, 200)
                b = random.randint(1, a)
                answer = a - b
            else:
                a = random.randint(50, 200)
                b = random.randint(50, 200)
                answer = a + b

        # Store the answer in session for checking later (future feature)
        problem = f"What is {a} {op} {b}?"
        prompts = [
            f"Here's a math problem for you: {problem}",
            f"Try this one: {problem}",
            f"Math time! {problem}",
            f"Okay, here we go: {problem}",
        ]
        return random.choice(prompts)

    async def _handle_bedtime_countdown(self, context: dict[str, Any]) -> str:
        """Calculate time until bedtime based on speaker's profile."""
        speaker = context.get("speaker", "").lower()
        now = datetime.now()

        # Default bedtimes by person (can be overridden by profile)
        default_bedtimes = {
            "viola": "19:30",      # 7:30 PM
            "zachary": "19:30",   # 7:30 PM
            "penelope": "20:30",  # 8:30 PM
            "xander": "21:00",    # 9:00 PM
            "thom": "22:30",      # 10:30 PM
            "elizabeth": "22:30", # 10:30 PM
        }

        # Try to get from profile first (future enhancement)
        # For now, use defaults based on speaker
        bedtime_str = None

        # Fall back to default
        if not bedtime_str:
            bedtime_str = default_bedtimes.get(speaker, "21:00")

        try:
            # Parse bedtime
            hour, minute = map(int, bedtime_str.replace("am", "").replace("pm", "").replace(":", " ").split()[:2])
            if "pm" in bedtime_str.lower() and hour != 12:
                hour += 12
            elif "am" in bedtime_str.lower() and hour == 12:
                hour = 0

            bedtime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If bedtime has passed today, it's tomorrow's bedtime
            if now > bedtime:
                return "It's past bedtime! Time for sleep!"

            # Calculate time remaining
            delta = bedtime - now
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60

            if hours > 0 and minutes > 0:
                time_str = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
            elif hours > 0:
                time_str = f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                time_str = f"{minutes} minute{'s' if minutes != 1 else ''}"

            responses = [
                f"You have {time_str} until bedtime!",
                f"Bedtime is in {time_str}.",
                f"{time_str} left until bedtime!",
            ]
            return random.choice(responses)

        except Exception as e:
            logger.warning(f"Failed to calculate bedtime: {e}")
            return "I'm not sure when bedtime is. Ask mom or dad!"

    def _handle_trivia(self, context: dict[str, Any]) -> str:
        """Ask a trivia question based on speaker's age."""
        speaker = context.get("speaker", "").lower()

        # Determine difficulty based on speaker
        if speaker in ["viola", "zachary"]:
            difficulty = "easy"
        elif speaker in ["penelope", "xander"]:
            difficulty = "medium"
        else:
            difficulty = random.choice(["medium", "hard"])

        questions = TRIVIA_DATA.get(difficulty, TRIVIA_DATA.get("medium", []))
        if not questions:
            return "I don't have any trivia questions right now!"

        q = random.choice(questions)
        question = q.get("question", "")
        answer = q.get("answer", "")

        # Store the answer for later (could be used for follow-up)
        prompts = [
            f"Here's a trivia question: {question}",
            f"Trivia time! {question}",
            f"Test your knowledge: {question}",
        ]
        response = random.choice(prompts)
        response += f" (The answer is: {answer})"
        return response

    def _handle_would_you_rather(self) -> str:
        """Give a 'would you rather' question."""
        kid_friendly = WOULD_YOU_RATHER_DATA.get("kid_friendly", [])
        family = WOULD_YOU_RATHER_DATA.get("family", [])

        # Combine and pick randomly
        all_questions = kid_friendly + family
        if not all_questions:
            return "I don't have any would-you-rather questions right now!"

        question = random.choice(all_questions)
        return question

    def _handle_encouragement(self, text: str) -> str:
        """Give encouragement, compliments, or support based on what user needs."""
        text_lower = text.lower()

        if "down" in text_lower or "sad" in text_lower:
            responses = ENCOURAGEMENT_DATA.get("feeling_down", [])
        elif "motivate" in text_lower:
            responses = ENCOURAGEMENT_DATA.get("motivation", [])
        elif "encourage" in text_lower:
            responses = ENCOURAGEMENT_DATA.get("encouragement", [])
        else:
            # Default to compliments
            responses = ENCOURAGEMENT_DATA.get("compliments", [])

        if not responses:
            return "You're doing great! Keep it up!"

        return random.choice(responses)

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
            op = match.group(2).lower()
            b = float(match.group(3))

            # Map word operators to symbols
            op_map = {
                "plus": "+",
                "minus": "-",
                "times": "*",
                "multiplied by": "*",
                "x": "*",
                "divided by": "/",
            }
            op = op_map.get(op, op)

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

    # =========================================================================
    # Random Choice Handlers
    # =========================================================================

    def _handle_coin_flip(self) -> str:
        """Flip a coin and return the result."""
        result = random.choice(["Heads", "Tails"])
        template = random.choice(self.COIN_FLIP_RESPONSES)
        return template.format(result=result)

    def _handle_dice_roll(self, text: str) -> str:
        """Roll dice and return the result.

        Supports: "roll a dice", "roll a d20", "roll 2d6"
        """
        if self._dice_pattern is None:
            return "You rolled a " + str(random.randint(1, 6)) + "!"

        match = self._dice_pattern.search(text)
        if match:
            # Check for dX format (e.g., d20)
            if match.group(1):
                sides = int(match.group(1))
                result = random.randint(1, sides)
            # Check for XdY format (e.g., 2d6)
            elif match.group(2) and match.group(3):
                num_dice = int(match.group(2))
                sides = int(match.group(3))
                rolls = [random.randint(1, sides) for _ in range(num_dice)]
                if num_dice > 1:
                    result = sum(rolls)
                    roll_str = " + ".join(map(str, rolls))
                    return f"You rolled {roll_str} = {result}!"
                result = rolls[0]
            else:
                # Standard d6
                result = random.randint(1, 6)
        else:
            # Default to d6
            result = random.randint(1, 6)

        template = random.choice(self.DICE_ROLL_RESPONSES)
        return template.format(result=result)

    def _handle_number_pick(self, text: str) -> str:
        """Pick a random number from a range."""
        if self._number_pick_pattern is None:
            result = random.randint(1, 10)
        else:
            match = self._number_pick_pattern.search(text)
            if match:
                low = int(match.group(1))
                high = int(match.group(2))
                if low > high:
                    low, high = high, low
                result = random.randint(low, high)
            else:
                result = random.randint(1, 10)

        template = random.choice(self.NUMBER_PICK_RESPONSES)
        return template.format(result=result)

    def _handle_yes_no(self) -> str:
        """Return a random yes or no."""
        return random.choice(self.YES_NO_RESPONSES)

    def _handle_magic_8_ball(self) -> str:
        """Return a magic 8-ball response."""
        return random.choice(MAGIC_8_BALL_RESPONSES)

    # =========================================================================
    # Unit Conversion Handlers
    # =========================================================================

    def _handle_unit_conversion(self, text: str) -> str | None:
        """Handle unit conversion queries."""
        text_lower = text.lower()

        # First check for "how many X in a Y" questions
        if self._unit_info_pattern:
            match = self._unit_info_pattern.search(text_lower)
            if match:
                unit_from = match.group(1).rstrip("s")
                unit_to = match.group(2).rstrip("s")
                # Try to find in UNIT_INFO
                for key, response in UNIT_INFO.items():
                    if unit_from in key[0] and unit_to in key[1]:
                        return response
                    if unit_to in key[0] and unit_from in key[1]:
                        return response

        # Check for temperature conversion
        if "fahrenheit" in text_lower and "celsius" in text_lower:
            # Extract number
            num_match = re.search(r"(\d+(?:\.\d+)?)", text)
            if num_match:
                value = float(num_match.group(1))
                if "to celsius" in text_lower or ("fahrenheit" in text_lower and text_lower.index("fahrenheit") < text_lower.index("celsius")):
                    # F to C
                    result = (value - 32) * 5/9
                    return f"That's about {result:.1f} degrees Celsius."
                else:
                    # C to F
                    result = value * 9/5 + 32
                    return f"That's about {result:.1f} degrees Fahrenheit."

        # Check for other unit conversions
        if self._unit_convert_pattern:
            match = self._unit_convert_pattern.search(text_lower)
            if match:
                value = float(match.group(1))
                from_unit = match.group(2).lower().rstrip("s")
                to_unit = match.group(3).lower().rstrip("s")

                # Normalize units
                if from_unit == "foot":
                    from_unit = "feet"
                if to_unit == "foot":
                    to_unit = "feet"

                # Look up conversion
                key = (from_unit + "s", to_unit + "s")
                if key in UNIT_CONVERSIONS:
                    factor, unit_name = UNIT_CONVERSIONS[key]
                    result = value * factor
                    if result == int(result):
                        result_str = str(int(result))
                    else:
                        result_str = f"{result:.2f}".rstrip("0").rstrip(".")
                    return f"That's {result_str} {unit_name}."

                # Try alternate key forms
                for conv_key, (factor, unit_name) in UNIT_CONVERSIONS.items():
                    if from_unit in conv_key[0] and to_unit in conv_key[1]:
                        result = value * factor
                        if result == int(result):
                            result_str = str(int(result))
                        else:
                            result_str = f"{result:.2f}".rstrip("0").rstrip(".")
                        return f"That's {result_str} {unit_name}."

        return None

    # =========================================================================
    # World Clock Handler
    # =========================================================================

    def _handle_world_clock(self, text: str) -> str | None:
        """Handle world clock queries."""
        if self._world_clock_pattern is None:
            return None

        match = self._world_clock_pattern.search(text)
        if not match:
            return None

        location = match.group(1).strip().lower()

        # Look up timezone
        tz_name = TIMEZONE_ALIASES.get(location)
        if not tz_name:
            # Try partial match
            for alias, tz in TIMEZONE_ALIASES.items():
                if alias in location or location in alias:
                    tz_name = tz
                    break

        if not tz_name:
            return f"I don't know the timezone for {location}. Try a major city like Tokyo, London, or New York."

        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            time_str = now.strftime("%I:%M %p").lstrip("0")
            day_str = now.strftime("%A")
            return f"It's {time_str} on {day_str} in {location.title()}."
        except Exception:
            return f"I couldn't get the time for {location}."

    # =========================================================================
    # Countdown Handler
    # =========================================================================

    def _handle_countdown(self, text: str) -> str | None:
        """Handle countdown to event queries."""
        if self._countdown_pattern is None:
            return None

        match = self._countdown_pattern.search(text.lower())
        if not match:
            return None

        event = match.group(1).strip().lower()

        # Check for known holidays
        target_date = None
        today = date.today()

        if event in HOLIDAYS:
            holiday_info = HOLIDAYS[event]
            if holiday_info:
                month, day = holiday_info
                target_date = date(today.year, month, day)
                # If the date has passed this year, use next year
                if target_date < today:
                    target_date = date(today.year + 1, month, day)
            else:
                # Special calculated holidays
                if "easter" in event:
                    target_date = self._calculate_easter(today.year)
                    if target_date < today:
                        target_date = self._calculate_easter(today.year + 1)
                elif "thanksgiving" in event:
                    target_date = self._calculate_thanksgiving(today.year)
                    if target_date < today:
                        target_date = self._calculate_thanksgiving(today.year + 1)
                elif "mother" in event:
                    target_date = self._calculate_mothers_day(today.year)
                    if target_date < today:
                        target_date = self._calculate_mothers_day(today.year + 1)
                elif "father" in event:
                    target_date = self._calculate_fathers_day(today.year)
                    if target_date < today:
                        target_date = self._calculate_fathers_day(today.year + 1)

        if target_date:
            days = (target_date - today).days
            event_name = event.title()
            if days == 0:
                return f"{event_name} is today!"
            elif days == 1:
                return f"{event_name} is tomorrow!"
            else:
                return f"{days} days until {event_name}!"

        return None

    def _calculate_easter(self, year: int) -> date:
        """Calculate Easter Sunday using the Anonymous Gregorian algorithm."""
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    def _calculate_thanksgiving(self, year: int) -> date:
        """Calculate Thanksgiving (4th Thursday in November)."""
        nov1 = date(year, 11, 1)
        # Find first Thursday
        days_until_thursday = (3 - nov1.weekday()) % 7
        first_thursday = nov1.day + days_until_thursday
        # 4th Thursday
        thanksgiving_day = first_thursday + 21
        return date(year, 11, thanksgiving_day)

    def _calculate_mothers_day(self, year: int) -> date:
        """Calculate Mother's Day (2nd Sunday in May)."""
        may1 = date(year, 5, 1)
        days_until_sunday = (6 - may1.weekday()) % 7
        first_sunday = may1.day + days_until_sunday
        second_sunday = first_sunday + 7
        return date(year, 5, second_sunday)

    def _calculate_fathers_day(self, year: int) -> date:
        """Calculate Father's Day (3rd Sunday in June)."""
        jun1 = date(year, 6, 1)
        days_until_sunday = (6 - jun1.weekday()) % 7
        first_sunday = jun1.day + days_until_sunday
        third_sunday = first_sunday + 14
        return date(year, 6, third_sunday)

    # =========================================================================
    # Counting Handler
    # =========================================================================

    def _handle_counting(self, text: str) -> str | None:
        """Handle counting requests."""
        text_lower = text.lower()

        # Check for "what comes after X"
        if self._next_number_pattern:
            match = self._next_number_pattern.search(text_lower)
            if match:
                num = int(match.group(1))
                if "before" in text_lower:
                    return f"{num - 1}!"
                return f"{num + 1}!"

        # Check for counting pattern
        if self._counting_pattern:
            match = self._counting_pattern.search(text_lower)
            if match:
                backwards = match.group(1) is not None
                start = int(match.group(2)) if match.group(2) else (10 if backwards else 1)
                end = int(match.group(3)) if match.group(3) else (1 if backwards else 10)
                step = int(match.group(4)) if match.group(4) else 1

                # Generate the count
                if backwards:
                    numbers = list(range(start, end - 1, -step))
                else:
                    numbers = list(range(start, end + 1, step))

                # Limit to reasonable length
                if len(numbers) > 50:
                    return "That's a lot of counting! Let's stick to smaller numbers."

                numbers_str = ", ".join(map(str, numbers))
                template = random.choice(self.COUNTING_RESPONSES)
                return template.format(numbers=numbers_str)

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
