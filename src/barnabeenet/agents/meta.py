"""Meta Agent - Request classification, context evaluation, and routing.

The Meta Agent is the cognitive pre-processor that evaluates every request.
Based on SkyrimNet's "evaluate first, route second" pattern.

Responsibilities:
1. Intent Classification & Routing - Determine request type and target agent
2. Context & Mood Evaluation - Analyze emotional tone, urgency, empathy needs
3. Memory Query Generation - Generate semantic search queries for memory retrieval

Now uses LogicRegistry for pattern definitions (editable via dashboard).
Also integrates DecisionRegistry for full decision tracing.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from barnabeenet.agents.base import Agent
from barnabeenet.services.llm.openrouter import OpenRouterClient

if TYPE_CHECKING:
    from barnabeenet.core.logic_registry import LogicRegistry

logger = logging.getLogger(__name__)


class IntentCategory(Enum):
    """Intent classification categories."""

    INSTANT = "instant"  # Time, date, simple status
    ACTION = "action"  # Device control, automation
    QUERY = "query"  # Information queries
    CONVERSATION = "conversation"  # Complex dialogue
    MEMORY = "memory"  # Remember/recall operations
    EMERGENCY = "emergency"  # Safety-critical
    GESTURE = "gesture"  # Physical input from wearable
    SELF_IMPROVEMENT = "self_improvement"  # Code fixes, improvements, bugs
    UNKNOWN = "unknown"


class UrgencyLevel(Enum):
    """Urgency classification for requests."""

    LOW = "low"  # Normal conversation, can wait
    MEDIUM = "medium"  # Time-sensitive but not critical
    HIGH = "high"  # Requires immediate attention
    EMERGENCY = "emergency"  # Safety-critical, interrupt everything


class EmotionalTone(Enum):
    """Detected emotional tone of requests."""

    NEUTRAL = "neutral"
    POSITIVE = "positive"  # Happy, excited, grateful
    NEGATIVE = "negative"  # Frustrated, sad, worried
    STRESSED = "stressed"  # Overwhelmed, anxious
    CONFUSED = "confused"  # Needs clarification
    URGENT = "urgent"  # Demanding immediate action


@dataclass
class ContextEvaluation:
    """Result of context and mood evaluation."""

    emotional_tone: EmotionalTone
    urgency_level: UrgencyLevel
    empathy_needed: bool
    detected_emotions: list[str] = field(default_factory=list)
    stress_indicators: list[str] = field(default_factory=list)
    suggested_response_tone: str = "friendly"
    confidence: float = 0.0
    evaluation_time_ms: int = 0


@dataclass
class MemoryQuerySet:
    """Generated queries for memory retrieval."""

    primary_query: str
    secondary_queries: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    relevant_people: list[str] = field(default_factory=list)
    time_context: str | None = None
    memory_types: list[str] = field(default_factory=list)
    confidence: float = 0.0
    generation_time_ms: int = 0


@dataclass
class ClassificationResult:
    """Complete result from Meta Agent processing."""

    intent: IntentCategory
    confidence: float
    sub_category: str | None = None
    context: ContextEvaluation | None = None
    memory_queries: MemoryQuerySet | None = None
    target_agent: str | None = None
    priority: int = 5  # 1-10, higher = more urgent
    total_processing_time_ms: int = 0
    matched_pattern: str | None = None  # The pattern/rule that triggered this classification

    # Diagnostic information for debugging
    classification_method: str | None = None  # "pattern", "heuristic", "llm"
    patterns_checked: int = 0
    near_miss_patterns: list[str] = field(default_factory=list)  # Patterns that almost matched
    failure_diagnosis: str | None = None  # Why pattern match failed (if applicable)
    diagnostics_summary: dict[str, Any] | None = None  # Full diagnostics if available


@dataclass
class MetaAgentConfig:
    """Configuration for Meta Agent behavior."""

    # Intent Classification
    pattern_match_confidence_threshold: float = 0.9
    heuristic_confidence_threshold: float = 0.7
    llm_classification_timeout_ms: int = 500

    # Context Evaluation
    context_evaluation_enabled: bool = True
    empathy_detection_sensitivity: float = 0.6

    # Urgency and stress detection keywords
    urgency_keywords: list[str] = field(
        default_factory=lambda: [
            "emergency",
            "urgent",
            "help",
            "now",
            "immediately",
            "quick",
            "asap",
            "hurry",
            "critical",
            "important",
        ]
    )
    stress_indicators: list[str] = field(
        default_factory=lambda: [
            "frustrated",
            "annoyed",
            "tired",
            "exhausted",
            "overwhelmed",
            "stressed",
            "worried",
            "anxious",
            "upset",
        ]
    )

    # Memory Query Generation
    memory_query_generation_enabled: bool = True
    max_secondary_queries: int = 3
    memory_query_timeout_ms: int = 300


# Pattern definitions for fast classification
INSTANT_PATTERNS: list[tuple[str, str]] = [
    # Time queries (including variations)
    (r"^(what('s| is) (the )?)?(current )?time(\?)?$", "time"),
    (r"^what time is it(\?)?$", "time"),
    (r"^what time(\?)?$", "time"),
    (r"^tell me the time(\?)?$", "time"),
    (r"^current time(\?)?$", "time"),
    # Date queries (including variations)
    (r"^(what('s| is) (the )?)?(today'?s? )?date(\?)?$", "date"),
    (r"^what date is it(\?)?$", "date"),
    (r"^what date(\?)?$", "date"),
    (r"^tell me the date(\?)?$", "date"),
    (r"^current date(\?)?$", "date"),
    (r"^(hello|hey|hi)( barnabee)?(\?)?$", "greeting"),
    (r"^good (morning|afternoon|evening|night)$", "greeting"),
    (r"^(what('s| is) )?(\d+)\s*[\+\-\*\/]\s*(\d+)(\?)?$", "math"),
    (r"^(what('s| is) )?(\d+)\s+(times|plus|minus|x)\s+(\d+)(\?)?$", "math"),
    (r"^(what('s| is) )?(\d+)\s+(divided by|multiplied by)\s+(\d+)(\?)?$", "math"),
    (r"^(how are you|you okay)(\?)?$", "status"),
    (r"^thank(s| you).*$", "thanks"),
    # Mic check / test queries
    (r"^(can you hear me|do you hear me|are you there|testing)(\?)?$", "mic_check"),
    # Clear conversation / Start fresh commands
    (r"^start\s*fresh$", "clear_conversation"),
    (r"^forget\s+this\s+conversation$", "clear_conversation"),
    (r"^clear\s+(the\s+)?conversation$", "clear_conversation"),
    (r"^new\s+conversation$", "clear_conversation"),
    (r"^reset\s+(our\s+)?(conversation|chat)$", "clear_conversation"),
    (r"^let'?s?\s+start\s+over$", "clear_conversation"),
    (r"^wipe\s+(the\s+)?slate\s+clean$", "clear_conversation"),
    (r"^test(ing)?( 1 2 3)?(\?)?$", "mic_check"),
    (r"^(is this|this is|am i) (working|on)(\?)?$", "mic_check"),
    # Random choices / games
    (r"^flip (a )?coin(\?)?$", "coin_flip"),
    (r"^(heads or tails|coin flip)(\?)?$", "coin_flip"),
    (r"^roll (a )?(dice|die|d\d+)(\?)?$", "dice_roll"),
    (r"^roll (\d+)d(\d+)(\?)?$", "dice_roll"),
    (r"^throw (a )?(dice|die)(\?)?$", "dice_roll"),
    (r"^yes or no(\?)?$", "yes_no"),
    (r"^(magic )?8[- ]?ball(\?)?$", "magic_8_ball"),
    (r"^magic eight ball(\?)?$", "magic_8_ball"),
    (r"^pick (a )?(random )?number.*$", "number_pick"),
    (r"^give me a (random )?number.*$", "number_pick"),
    # World clock
    (r"^what('?s| is) (the )?time in .+(\?)?$", "world_clock"),
    (r"^(what time|tell me the time) (?:is it )?in .+(\?)?$", "world_clock"),
    # Sun queries (BEFORE countdown to avoid generic "when is" matching)
    (r"^when (is|does) (sunrise|sunset|dawn|dusk)(\?)?$", "sun"),
    (r"^when does the sun (rise|set)(\?)?$", "sun"),
    (r"^what time is (sunrise|sunset|dawn|dusk)(\?)?$", "sun"),
    # Countdown to events (after sun to avoid matching "when is sunrise")
    (r"^how (many|long) (days? )?(until|till|to|before) .+(\?)?$", "countdown"),
    (r"^(days? )?(until|till|to) .+(\?)?$", "countdown"),
    (r"^when is .+(\?)?$", "countdown"),
    # Counting
    (r"^count (to|from|backwards?|down) .*$", "counting"),
    (r"^count by \d+s? .*$", "counting"),
    (r"^what('?s| is| comes?)? (after|before|next after) \d+(\?)?$", "counting"),
    # Unit conversions
    (r"^convert \d+.* to .*$", "unit_conversion"),
    (r"^how many (cups?|liters?|ounces?|inches?|feet|foot|centimeters?|grams?|tablespoons?|teaspoons?) .*$", "unit_conversion"),
    (r"^\d+ (fahrenheit|celsius|cups?|liters?|pounds?|kilograms?|ounces?|inches?|feet|foot|meters?|miles?) (to|in) .*$", "unit_conversion"),
    # Undo last action
    (r"^undo( that)?(\?)?$", "undo"),
    (r"^(reverse|take back) that(\?)?$", "undo"),
    (r"^never ?mind$", "undo"),
    # Repeat / Say that again
    (r"^(say|repeat) (that|it)( again)?(\?)?$", "repeat"),
    (r"^repeat that(\?)?$", "repeat"),
    (r"^what did you say(\?)?$", "repeat"),
    (r"^come again(\?)?$", "repeat"),
    (r"^(pardon)(\?)?$", "repeat"),
    (r"^i didn'?t (hear|catch) (that|you)(\?)?$", "repeat"),
    (r"^one more time(\?)?$", "repeat"),
    # Jokes
    (r"^tell me a( \w+)? joke(\?)?$", "joke"),
    (r"^(got a|another|one more) joke(\?)?$", "joke"),
    (r"^joke please(\?)?$", "joke"),
    (r"^make me laugh(\?)?$", "joke"),
    # Riddles
    (r"^tell me a riddle(\?)?$", "riddle"),
    (r"^(give me|got) a riddle(\?)?$", "riddle"),
    (r"^riddle me this(\?)?$", "riddle"),
    # Fun facts
    (r"^tell me a( \w+)? (fun )?fact(\?)?$", "fun_fact"),
    (r"^tell me a fact about \w+(\?)?$", "fun_fact"),
    (r"^(fun|interesting|cool) fact(\?)?$", "fun_fact"),
    (r"^did you know(\?)?$", "fun_fact"),
    (r"^tell me something (interesting|cool|fun)(\?)?$", "fun_fact"),
    (r"^fact about \w+(\?)?$", "fun_fact"),
    # Animal sounds
    (r"^what does a \w+ say(\?)?$", "animal_sound"),
    (r"^what do \w+s? say(\?)?$", "animal_sound"),
    (r"^what sound does a \w+ make(\?)?$", "animal_sound"),
    (r"^how does a \w+ (go|sound)(\?)?$", "animal_sound"),
    (r"^what noise does a \w+ make(\?)?$", "animal_sound"),
    # Math practice
    (r"^(give me a |)math (problem|question)(\?)?$", "math_practice"),
    (r"^quiz me( on math)?(\?)?$", "math_practice"),
    (r"^test me( on math)?(\?)?$", "math_practice"),
    (r"^(math|number) practice(\?)?$", "math_practice"),
    (r"^practice math(\?)?$", "math_practice"),
    # Bedtime countdown
    (r"^(how long|how much time) until bedtime(\?)?$", "bedtime"),
    (r"^when is (my )?bedtime(\?)?$", "bedtime"),
    (r"^bedtime countdown(\?)?$", "bedtime"),
    (r"^how much longer until bed(\?)?$", "bedtime"),
    (r"^when do i (go to|have to go to) bed(\?)?$", "bedtime"),
    # Trivia
    (r"^(ask me a |give me a )?(trivia|quiz) question(\?)?$", "trivia"),
    (r"^trivia( time)?(\?)?$", "trivia"),
    (r"^test my knowledge(\?)?$", "trivia"),
    # Would you rather
    (r"^would you rather(\?)?$", "would_you_rather"),
    (r"^give me a would you rather(\?)?$", "would_you_rather"),
    # Encouragement / compliments
    (r"^(give me a |)compliment(\?)?$", "encouragement"),
    (r"^say something nice(\?)?$", "encouragement"),
    (r"^(i('m| am) feeling down|i feel sad)(\?)?$", "encouragement"),
    (r"^cheer me up(\?)?$", "encouragement"),
    (r"^motivate me(\?)?$", "encouragement"),
    (r"^(i need |)encouragement(\?)?$", "encouragement"),
    # Location queries
    (r"^where('s| is) \w+(\?)?$", "location"),
    (r"^is \w+ (home|at home)(\?)?$", "location"),
    (r"^where are \w+(\?)?$", "location"),
    (r"^(find|locate) \w+(\?)?$", "location"),
    (r"^\w+'s location(\?)?$", "location"),
    # Who's home queries
    (r"^who('s| is) (home|at home|here)(\?)?$", "whos_home"),
    (r"^is (anyone|anybody|everyone|everybody) (home|at home)(\?)?$", "whos_home"),
    (r"^(anyone|anybody) home(\?)?$", "whos_home"),
    (r"^is the house empty(\?)?$", "whos_home"),
    # Device status queries
    (r"^is the \w+( \w+)? (on|off|open|closed|locked|unlocked)(\?)?$", "device_status"),
    (r"^is \w+( \w+)? (on|off|open|closed|locked|unlocked)(\?)?$", "device_status"),
    (r"^(status of|check) the \w+( \w+)?(\?)?$", "device_status"),
    (r"^what('s| is) the \w+( \w+)? (set to|at|temperature)(\?)?$", "device_status"),
    # Moon queries
    (r"^(what('s| is) the |)moon phase(\?)?$", "moon"),
    (r"^what phase is the moon( in)?(\?)?$", "moon"),
    (r"^(moon|lunar) phase tonight(\?)?$", "moon"),
    # Weather queries
    (r"^(what('s| is) the |)weather(\?)?$", "weather"),
    (r"^(what('s| is) the |)temperature( outside)?(\?)?$", "weather"),
    (r"^how (cold|hot|warm) is it( outside)?(\?)?$", "weather"),
    (r"^(will it|is it going to) rain(\?)?$", "weather"),
    (r"^is it raining(\?)?$", "weather"),
    (r"^do i need (an |)umbrella(\?)?$", "weather"),
    (r"^(will it|is it going to) snow(\?)?$", "weather"),
    (r"^is it snowing(\?)?$", "weather"),
    (r"^(what('s| is) the |)forecast(\?)?$", "weather"),
    # Shopping list
    (r"^(add|put) .+ (to |on )(the |my )?(shopping list|groceries)(\?)?$", "shopping_list"),
    (r"^what('s| is) on (the |my )?(shopping list|groceries)(\?)?$", "shopping_list"),
    (r"^(read|show)( me)? (the |my )?(shopping list|groceries)(\?)?$", "shopping_list"),
    (r"^(clear|empty) (the |my )?(shopping list|groceries)(\?)?$", "shopping_list"),
    (r"^(remove|take off|cross off) .+ (from |off )(the |my )?(shopping list|groceries)(\?)?$", "shopping_list"),
    # Calendar queries
    (r"^what('s| is) on (the |my )?(calendar|schedule)( today| tomorrow| this week)?(\?)?$", "calendar"),
    (r"^(what do i|what do we) have (today|tomorrow|this week|scheduled)(\?)?$", "calendar"),
    (r"^(any|do i have any) (appointments?|events?|plans?) (today|tomorrow|this week)?(\?)?$", "calendar"),
    (r"^what('s| is) (happening|scheduled)( today| tomorrow| this week)?(\?)?$", "calendar"),
    (r"^(when is|what is) (the |my )?next (event|appointment)(\?)?$", "calendar"),
    # Security queries (locks, blinds)
    (r"^(is |are )(the )?(front )?(door|doors) (locked|unlocked)(\?)?$", "security"),
    (r"^(is |are )(the |any )?(blind|blinds|shade|shades) (open|closed)(\?)?$", "security"),
    (r"^(are all|check) (the )?(doors|locks|blinds)(\?)?$", "security"),
    (r"^(lock|unlock) (status|check)(\?)?$", "security"),
    (r"^(security|secure) (status|check)(\?)?$", "security"),
    # Phone battery queries
    (r"^(is |what('s| is) )(\w+('s)? )?phone (battery|charged|charge)(\?)?$", "phone_battery"),
    (r"^(how much |what('s| is) (the |my |))(battery|charge) (on |in )?(my |\w+'s )?phone(\?)?$", "phone_battery"),
    (r"^phone batter(y|ies)(\?)?$", "phone_battery"),
    (r"^(is |does )(\w+('s)? )?phone need(s)? charg(ed|ing)(\?)?$", "phone_battery"),
    # Energy queries
    (r"^(how much |what('s| is) (the |our )?)(energy|power|electricity)( usage| consumption)?(\?)?$", "energy"),
    (r"^(how much |what('s| is) )(energy|power) (are we using|did we use)(\?)?$", "energy"),
    (r"^(what('s| is) |)(our |the )?(energy|power|electricity) (usage|consumption)?( today| this month)?(\?)?$", "energy"),
    (r"^(how('s| is) )(the |our )?solar( doing| production)?(\?)?$", "energy"),
    (r"^how much (energy|power)( did we use)? today(\?)?$", "energy"),
    (r"^(energy|power) (today|this month)(\?)?$", "energy"),
    (r"^(energy|power) usage( today| this month)?(\?)?$", "energy"),
    # Pet feeding queries
    (r"^(did anyone |did someone |has anyone )(feed|fed) (the )?(dog|cat|fish|hamster|rabbit|bird|pet)(\?)?$", "pet_feeding"),
    (r"^(i |i'?ve |we )(fed|just fed) (the )?(dog|cat|fish|hamster|rabbit|bird|pet)(\?)?$", "pet_feeding"),
    (r"^(has |was )(the )?(dog|cat|fish|hamster|rabbit|bird|pet) been fed(\?)?$", "pet_feeding"),
    (r"^(when was |when did ).*(the )?(dog|cat|fish|hamster|rabbit|bird|pet) (last |)fed(\?)?$", "pet_feeding"),
    (r"^(log that i fed|log feeding|record feeding) (the )?(dog|cat|fish|hamster|rabbit|bird|pet)(\?)?$", "pet_feeding"),
    (r"^did (the |)(dog|cat|fish|hamster|rabbit|bird|pet) (get |)fed(\?)?$", "pet_feeding"),
    (r"^fed (the )?(dog|cat|fish|hamster|rabbit|bird|pet)(\?)?$", "pet_feeding"),
    # Quick notes
    (r"^note[:\s]+.+$", "quick_note"),
    (r"^remember[:\s]+.+$", "quick_note"),
    (r"^remind me[:\s]+.+$", "quick_note"),
    (r"^(make a|save (a |))note[:\s]+.+$", "quick_note"),
    (r"^(what are|show|list|read) (my )?notes(\?)?$", "quick_note"),
    (r"^(my |)notes( about .+)?(\?)?$", "quick_note"),
    # Chore/Star tracking
    (r"^(give|award|add) (\w+ )?(a )?star( to \w+)?(\?)?$", "chore"),
    (r"^how many stars (does |do )?\w+ have(\?)?$", "chore"),
    (r"^(\w+('s|s) )?stars?(\?)?$", "chore"),
    (r"^check (\w+('s|s) )?stars?(\?)?$", "chore"),
    (r"^\w+ (finished|did|completed|done with) (the |her |his |their )?(homework|dishes|chore|room|trash|laundry)(\?)?$", "chore"),
    (r"^(whose|who'?s) turn (to |for )(do |)(the )?(dishes|trash|chores?|laundry)(\?)?$", "chore"),
    (r"^who should (do|take out) (the )?(dishes|trash|chores?|laundry)(\?)?$", "chore"),
    (r"^(what |)chores? (are |)(left|today|remaining)(\?)?$", "chore"),
    # Focus/Pomodoro timer
    (r"^start (a )?(pomodoro|focus( time| session)?|homework time|study time|work session)(\?)?$", "focus_timer"),
    (r"^(begin|let'?s (start|do)) (a )?(pomodoro|focus|homework|study)( time| session)?(\?)?$", "focus_timer"),
    (r"^(how long|how much time) (have i been|left) (studying|focusing|working)(\?)?$", "focus_timer"),
    (r"^(stop|end|finish|done with) (the )?(pomodoro|focus|study|homework)( session| time)?(\?)?$", "focus_timer"),
    # WiFi password
    (r"^(what('s| is) (the )?)?wifi (password|pass|code)(\?)?$", "wifi"),
    (r"^(what('s| is) (the )?)?(guest )?(wifi|wi-fi|network) (password|pass|credentials)(\?)?$", "wifi"),
    (r"^(how do i |can i )connect to (the )?(wifi|wi-fi|internet)(\?)?$", "wifi"),
    # Family digest / what happened
    (r"^what happened (today|at home|this morning|this evening|while i was (gone|out|away))(\?)?$", "family_digest"),
    (r"^(catch me up|fill me in)(\?)?$", "family_digest"),
    (r"^what did i miss(\?)?$", "family_digest"),
    (r"^(family |home )?digest(\?)?$", "family_digest"),
    # Spelling queries
    (r"^(?:how (?:do (?:you |i )?)?)?spell (\w+)(\?)?$", "spelling"),
    (r"^(?:can you |please )?spell(?: me)? (\w+)(\?)?$", "spelling"),
    (r"^what(?:'s| is) the spelling of (\w+)(\?)?$", "spelling"),
    (r"^how do you spell (\w+)(\?)?$", "spelling"),
    (r"^how do i spell (\w+)(\?)?$", "spelling"),
    (r"^spell out (\w+)(\?)?$", "spelling"),
    # Spelling continuation - short affirmative responses for letter-by-letter mode
    (r"^(yes|yeah|yep|yup|sure|ok|okay)(\?)?$", "spelling_continue"),
    (r"^(next|continue|go on|go ahead)(\?)?$", "spelling_continue"),
    (r"^(next letter|what'?s next|and|then|more|another)(\?)?$", "spelling_continue"),
    (r"^(no|nope|stop|cancel|done|nevermind|never mind)$", "spelling_continue"),
]

ACTION_PATTERNS: list[tuple[str, str]] = [
    # Timer patterns FIRST (before other patterns that might conflict)
    (r"^(set|start) (a )?timer .*$", "timer"),
    (r"^(set|start) (a )?(\w+) timer .*$", "timer"),
    (r"^(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+timer$", "timer"),
    (r"^(turn|switch) (on|off) .+ (for|in) .+$", "timer"),  # "turn on light for 5 minutes"
    (r"^in\s+(\d+\s*(?:seconds?|secs?|minutes?|mins?))\s+turn\s+(?:off|on)\s+.*$", "timer"),  # "in 60 seconds turn off light"
    (r"^wait\s+(\d+\s*(?:seconds?|secs?|minutes?|mins?))\s+turn\s+(?:off|on)\s+.*$", "timer"),  # "wait 3 minutes turn on fan"
    (r"^how\s+long\s+(?:on|for|left\s+on)\s+.*$", "timer"),  # "how long on lasagna"
    (r"^how\s+much\s+time\s+left\s+(?:on|for)\s+.*$", "timer"),  # "how much time left on pizza"
    (r"^time\s+left\s+(?:on|for)\s+.*$", "timer"),  # "time left on lasagna"
    (r"^(pause|resume|cancel|stop|start)\s+(?:the\s+)?.*(?:\s+timer)?$", "timer"),  # "pause the lasagna timer" - MUST come before media patterns
    # Timer list/query patterns
    (r"^what\s+timers?.*$", "timer"),  # "what timers do I have"
    (r"^(?:list|show)\s+(?:my\s+)?timers?.*$", "timer"),  # "list my timers"
    (r"^how\s+long\s+(?:is\s+)?left\s+on\s+(?:my|the)\s+timer.*$", "timer"),  # "how long is left on my timer"
    (r"^how\s+much\s+time\s+(?:is\s+)?left\s+on\s+(?:my|the)\s+timer.*$", "timer"),  # "how much time is left on my timer"
    (r"^(?:any|do\s+I\s+have(?:\s+any)?)\s+timers?.*$", "timer"),  # "any timers" / "do I have any timers"
    (r"^are\s+there\s+(?:any\s+)?timers?.*$", "timer"),  # "are there any timers"
    (r"^how\s+many\s+timers?.*$", "timer"),  # "how many timers do I have"
    (r"^timers?\s+status.*$", "timer"),  # "timer status"
    # Entity state query patterns - route to action agent for direct HA queries
    # Single entity state queries
    (r"^is (?:the |my )?(.+?) (on|off|open|closed|locked|unlocked)\??$", "entity_query"),
    # Area/domain aggregation queries
    (r"^(?:are|is) (?:there )?any (.+?) (on|off|open|closed|locked|unlocked).*$", "entity_query"),
    (r"^how many (.+?) (?:are )?(on|off|open|closed|in |outside|downstairs|upstairs).*$", "entity_query"),
    (r"^what (.+?) (?:are|is) (on|off|open|closed|locked|unlocked).*$", "entity_query"),
    (r"^which (.+?) (?:are|is) (on|off|open|closed|locked|unlocked).*$", "entity_query"),
    # Attribute queries (battery, unavailable)
    (r"^what (?:batteries|devices?) need (?:changing|replacing|charging).*$", "entity_query"),
    (r"^(?:which|what) (?:devices?|sensors?|batteries?) (?:are |have )?(?:low|dead|dying).*$", "entity_query"),
    (r"^(?:which|what) (?:devices?|entities?) (?:are )?unavailable.*$", "entity_query"),
    # List/show queries
    (r"^(?:list|show)(?: all)?(?: the)? (.+?) (?:that are )?(on|off|open|closed).*$", "entity_query"),
    (r"^(?:list|show)(?: all)?(?: the)? (.+?) (?:in |on )?(?:the )?(.+)$", "entity_query"),
    # Count queries
    (r"^how many (?:devices?|lights?|switches?|sensors?) (?:do i have |are )?(?:in |on )?(?:the )?(.+)$", "entity_query"),
    # Sensor value queries (temperature, humidity, power)
    (r"^what(?:'s| is) the (?:temperature|humidity|power|energy).*$", "entity_query"),
    (r"^how (?:hot|cold|warm|humid) is (?:it )?.*$", "entity_query"),
    # Climate/thermostat queries
    (r"^what(?:'s| is) the (?:thermostat|ac|heating|climate|hvac).*$", "entity_query"),
    (r"^(?:is|are) the (?:heating|cooling|ac|air conditioning) (?:on|off|running).*$", "entity_query"),
    (r"^what mode is the (?:thermostat|ac|hvac|climate).*$", "entity_query"),
    (r"^what(?:'s| is) the (?:target |set )?temperature\??$", "entity_query"),
    # Security queries
    (r"^(?:are|is) (?:all )?(?:the )?doors? (?:all )?locked\??$", "entity_query"),
    (r"^(?:are|is) (?:all )?(?:the )?windows? (?:all )?closed\??$", "entity_query"),
    (r"^(?:are|is) (?:any|the) doors? (?:unlocked|open)\??$", "entity_query"),
    (r"^(?:are|is) (?:any|the) windows? open\??$", "entity_query"),
    (r"^(?:is|are) the (?:house|home) (?:secure|locked|safe)\??$", "entity_query"),
    (r"^(?:is|are) the (?:alarm|security)(?: system)? (?:armed|on|set)\??$", "entity_query"),
    (r"^(?:is|are) the garage(?: door)? (?:open|closed)\??$", "entity_query"),
    (r"^security status\??$", "entity_query"),
    # Presence queries
    (r"^(?:is|are) (?:anyone|anybody|someone|somebody) (?:home|here|in)\??$", "entity_query"),
    (r"^(?:is|are) (?:everyone|everybody) (?:home|here|out|away|gone)\??$", "entity_query"),
    (r"^who(?:'s| is) (?:home|here|away|out)\??$", "entity_query"),
    (r"^(?:is|are) the (?:house|home) (?:empty|occupied)\??$", "entity_query"),
    (r"^how many (?:people|persons?) (?:are )?(?:home|here)\??$", "entity_query"),
    # Media queries
    (r"^what(?:'s| is) (?:playing|on)(?: (?:on |the )?(?:the )?.+)?\??$", "entity_query"),
    (r"^(?:is|are) (?:any )?(?:music|something|anything) playing\??$", "entity_query"),
    (r"^(?:is|are) the (?:tv|television|speaker|music|media)(?: player)? (?:on|playing)\??$", "entity_query"),
    (r"^what(?:'s| is) the volume.*$", "entity_query"),
    # Cover/blind queries
    (r"^(?:are|is) (?:the )?(?:blinds?|shades?|curtains?|covers?) (?:open|closed|up|down).*$", "entity_query"),
    (r"^what(?:'s| is) the (?:position|status) of (?:the )?(?:blinds?|shades?|curtains?|covers?).*$", "entity_query"),
    # Last changed queries
    (r"^when (?:was|did) (?:the )?.+? (?:last )?(?:opened|closed|changed|turned on|turned off).*$", "entity_query"),
    (r"^how long (?:has|have) (?:the )?.+? been (?:on|off|open|closed).*$", "entity_query"),
    # Brightness queries
    (r"^how bright (?:is|are) (?:the )?.+\??$", "entity_query"),
    (r"^what(?:'s| is) the brightness.*$", "entity_query"),
    (r"^(?:at )?what (?:level|percentage|percent) (?:is|are) (?:the )?.+.*$", "entity_query"),
    # Device control patterns
    (r"^(turn|trun|tunr|switch|swtich|swich) (on|off|of) .*$", "switch"),  # Common typos
    (r"^(on|off) .*(light|lamp|switch|fan).*$", "switch"),  # "off the light"
    (
        r".*(turn|trun|tunr|switch|swtich|swich) (on|off|of) (the |my |a )?.*$",
        "switch",
    ),  # Mid-sentence
    (r"^(set|change) .* to .*$", "set"),
    (r"^(dim|brighten) .*$", "light"),
    (r"^(lock|unlock) .*$", "lock"),
    (r"^(open|close|stop) .*(blind|shade|curtain|cover|garage|window).*$", "cover"),  # Stop covers
    (r"^(open|close) .*$", "cover"),
    (r"^(play|pause|stop|skip) .*$", "media"),  # Media control (pause/resume here won't match timer patterns above)
    (r"^activate .*$", "scene"),
    (r"^(start|stop) .* mode$", "mode"),
]

QUERY_PATTERNS: list[tuple[str, str]] = [
    (r"^(what('s| is) the )?(temperature|weather|humidity) .*$", "sensor"),
    (r"^(is|are) .* (on|off|open|closed|locked|unlocked)(\?)?$", "state"),
    (r"^(what|how much|how many) .*$", "query"),
    (r"^(when|where) .*$", "query"),
]

# Conversation patterns - for complex interactions that need InteractionAgent
# These use ^ anchor because _pattern_match uses pattern.match() which starts at beginning
CONVERSATION_PATTERNS: list[tuple[str, str]] = [
    # Super user / Audit log access (parents only)
    (r"^show\s+(me\s+)?(all|the)\s+(audit\s+)?(logs?|conversations?|history).*$", "audit_access"),
    (r"^(what\s+did\s+)?(everyone|the\s+kids?|they)\s+(say|talk\s+about|discuss).*$", "audit_access"),
    (r"^show\s+(me\s+)?deleted\s+(conversations?|messages?).*$", "audit_access"),
    (r"^(parent(al)?|audit)\s+(access|log|mode).*$", "audit_access"),
    (r"^full\s+(history|log|access).*$", "audit_access"),
    (r"^show\s+(me\s+)?alerts?.*$", "audit_access"),
    # Cross-device handoff
    (r"^continue\s+(the\s+)?conversation\s+.*(on|from)\s+.*$", "handoff"),
    (r"^pick\s+up\s+(where\s+I\s+left\s+off\s+)?(on|from)\s+.*$", "handoff"),
    (r"^(what\s+was\s+I|were\s+we)\s+(talking|discussing)\s+about\s+(on|in)\s+.*$", "handoff"),
    (r"^resume\s+(my\s+)?(conversation\s+)?(from\s+)?(the\s+)?.*$", "handoff"),
    # Recall with expansion
    (r"^tell\s+me\s+more$", "expand_recall"),
    (r"^more\s+details?$", "expand_recall"),
    (r"^(expand|full\s+conversation)$", "expand_recall"),
]

MEMORY_PATTERNS: list[tuple[str, str]] = [
    # Explicit store commands
    (r"^remember (that )?.*$", "store"),
    (r"^(please )?(store|save|keep|note) (that )?.*$", "store"),
    (
        r"^(can you |could you |will you |would you )?(please )?(remember|store|save|keep|note) (that )?.*$",
        "store",
    ),
    (r"^make a note (that )?.*$", "store"),
    (r"^don'?t forget (that )?.*$", "store"),
    # Forget/delete memory commands (route to conversation for handling)
    (r"^forget\s+about\s+.*conversation$", "forget"),
    (r"^forget\s+that$", "forget"),
    (r"^delete\s+(that|this)\s+(conversation|memory)$", "forget"),
    # Factual statements about preferences/information (implicit store)
    (r"^(my|our|\w+'s) (favorite|favourite) .+ (is|are) .+$", "store"),
    (r"^(the )?(secret|password|code|pin) (word )?(is|are) .+$", "store"),
    (r"^(my|our|\w+'s) .+ (is|are) .+$", "store"),  # "my birthday is...", "thom's car is..."
    (r"^(i|we) (like|love|prefer|hate|dislike|enjoy) .+$", "store"),
    (r"^(i|we) (am|are) .+$", "store"),  # "I am allergic to...", "we are vegetarian"
    # Recall patterns
    (r"^(do you remember|what do you know about) .*$", "recall"),
    (
        r"^(can you |could you |will you |would you )?(tell me )?(what|who|when|where).*(you remember|you know|stored|saved).*$",
        "recall",
    ),
    (r"^forget .*$", "forget"),
    (r"^(when|what) did (i|we) .*$", "recall"),
    (r".*(last thing|previously|earlier|before).*(ask|say|tell|said|told).*$", "recall"),
    (r".*(what|when) (was|were|have|had) (i|we) .*$", "recall"),
    (r"^what (was|were) (my|our) last .*$", "recall"),
    (r".*(asked|told) (you to |you )?(remember|store|save).*$", "recall"),
    (r".*what.*(remember|stored|saved).*$", "recall"),
    (r"^what('s| is| are) (my|our|\w+'s) (favorite|favourite) .+$", "recall"),
    (r"^what('s| is) the (secret|password|code|pin).*$", "recall"),
    (r"^(do you |can you )?(recall|recollect) .*$", "recall"),
    # Generic preference recall queries (new patterns)
    (r"^what do (i|we) (like|prefer|want|need)(\?)?$", "recall"),
    (r"^what('s| is) (my|our) preference(\?)?$", "recall"),
    (r"^what .+ do (i|we) prefer(\?)?$", "recall"),
    # Colon-separated remember statements
    (r"^remember:\s*.+$", "store"),
    (r"^note:\s*.+$", "store"),
]

GESTURE_PATTERNS: list[tuple[str, str]] = [
    (r"^crown_twist_(yes|no|up|down)$", "choice"),
    (r"^button_click_(confirm|cancel)$", "confirm"),
    (r"^motion_shake$", "dismiss"),
    (r"^double_tap$", "quick_action"),
]

EMERGENCY_PATTERNS: list[tuple[str, str]] = [
    (r".*(fire|smoke|burning|flames).*", "fire"),
    (r".*(help|emergency|911|ambulance).*", "emergency"),
    (r".*(intruder|break.?in|someone.?in.?the.?house).*", "security"),
    (r".*(fall|fallen|can'?t get up|hurt).*", "medical"),
]

SELF_IMPROVEMENT_PATTERNS: list[tuple[str, str]] = [
    # Explicit self-service keyword (highest priority)
    (r".*self[- ]?service.*", "self"),
    (r".*self[- ]?improve.*", "self"),
    (r".*use self.*", "self"),
    # Direct fix requests
    (r".*fix (this|that|it).*", "fix"),
    (r".*please fix.*", "fix"),
    (r".*(that'?s|it'?s|this is) broken.*", "fix"),
    (r".*(doesn'?t|does not|don'?t|do not) work.*", "fix"),
    (r".*not working.*", "fix"),
    (r".*(there'?s|there is) a bug.*", "fix"),
    (r".*(there'?s|there is) an? (issue|problem|error).*", "fix"),
    # Improvement requests
    (r".*improve (the |this |that |my )?.*", "improve"),
    (r".*enhance (the |this |that )?.*", "improve"),
    (r".*upgrade (the |this |that )?.*", "improve"),
    (r".*make .* better.*", "improve"),
    (r".*optimize (the |this |that )?.*", "improve"),
    # Self-referential
    (r".*(fix|improve|update|change) yourself.*", "self"),
    (r".*(fix|improve|update|change) your (own )?code.*", "self"),
    (r".*(fix|improve|update|change) barnabeenet.*", "self"),
    (r".*(fix|improve|update|change) barnabee.*", "self"),
    # Code changes
    (r".*(change|modify|update|edit) (the |this |that )?(code|file|source).*", "modify"),
    (r".*(add|implement|create) (a |the )?(new )?feature.*", "add"),
]

# Map intent categories to target agents
INTENT_TO_AGENT: dict[IntentCategory, str] = {
    IntentCategory.INSTANT: "instant",
    IntentCategory.ACTION: "action",
    IntentCategory.QUERY: "interaction",  # Complex queries go to interaction
    IntentCategory.CONVERSATION: "interaction",
    IntentCategory.MEMORY: "memory",
    IntentCategory.EMERGENCY: "action",  # Emergencies need immediate action
    IntentCategory.GESTURE: "instant",
    IntentCategory.SELF_IMPROVEMENT: "self_improvement",  # Code fixes and improvements
    IntentCategory.UNKNOWN: "interaction",  # Default to interaction
}


class MetaAgent(Agent):
    """Meta Agent with intent classification and context evaluation.

    The Meta Agent is the cognitive pre-processor that evaluates every request.
    It classifies intent, evaluates context/mood, and routes to the appropriate
    specialized agent.

    Supports two modes:
    1. LogicRegistry mode (new): Patterns loaded from config/patterns.yaml
    2. Legacy mode: Patterns from hardcoded lists (backward compatible)

    Now includes full decision tracing and diagnostics for debugging.
    """

    name = "meta"

    # Pattern priority for classification (used for diagnostics)
    PATTERN_PRIORITY: list[tuple[str, IntentCategory, float]] = [
        ("emergency", IntentCategory.EMERGENCY, 0.99),
        ("instant", IntentCategory.INSTANT, 0.95),
        ("gesture", IntentCategory.GESTURE, 0.95),
        ("self_improvement", IntentCategory.SELF_IMPROVEMENT, 0.92),
        ("conversation", IntentCategory.CONVERSATION, 0.92),  # Super user, handoff, recall
        ("action", IntentCategory.ACTION, 0.90),
        ("memory", IntentCategory.MEMORY, 0.90),
        ("query", IntentCategory.QUERY, 0.85),
    ]

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        config: MetaAgentConfig | None = None,
        logic_registry: LogicRegistry | None = None,
        enable_diagnostics: bool = True,
        enable_health_monitoring: bool = True,
    ) -> None:
        self._llm_client = llm_client
        self._config = config or MetaAgentConfig()
        self._logic_registry = logic_registry
        self._compiled_patterns: dict[str, list[tuple[re.Pattern[str], str]]] = {}
        self._use_registry = False  # Will be set during init
        self._enable_diagnostics = enable_diagnostics
        self._enable_health_monitoring = enable_health_monitoring
        self._diagnostics_service = None
        self._health_monitor = None

    async def init(self) -> None:
        """Initialize the Meta Agent - load patterns from registry or compile hardcoded."""
        # Try to use LogicRegistry if provided or available
        if self._logic_registry is None:
            try:
                from barnabeenet.core.logic_registry import get_logic_registry

                self._logic_registry = await get_logic_registry()
                self._use_registry = True
                logger.info("MetaAgent using LogicRegistry for patterns")
            except Exception as e:
                logger.debug("LogicRegistry not available, using hardcoded patterns: %s", e)
                self._use_registry = False

        # Initialize diagnostics service
        if self._enable_diagnostics:
            try:
                from barnabeenet.services.logic_diagnostics import get_diagnostics_service

                self._diagnostics_service = get_diagnostics_service()
                logger.info("MetaAgent diagnostics enabled")
            except Exception as e:
                logger.debug("Diagnostics service not available: %s", e)

        # Initialize health monitor
        if self._enable_health_monitoring:
            try:
                from barnabeenet.services.logic_health import get_health_monitor

                self._health_monitor = get_health_monitor()
                logger.info("MetaAgent health monitoring enabled")
            except Exception as e:
                logger.debug("Health monitor not available: %s", e)

        if self._use_registry and self._logic_registry:
            # Load patterns from registry
            for group_name in [
                "emergency",
                "instant",
                "gesture",
                "self_improvement",
                "conversation",
                "action",
                "memory",
                "query",
            ]:
                patterns = self._logic_registry.get_patterns_as_tuples(group_name)
                self._compiled_patterns[group_name] = [
                    (re.compile(p, re.IGNORECASE), c) for p, c in patterns
                ]

            # Check if registry actually loaded any patterns
            total_patterns = sum(len(p) for p in self._compiled_patterns.values())
            if total_patterns == 0:
                logger.warning("LogicRegistry loaded no patterns, falling back to hardcoded")
                self._use_registry = False
            else:
                logger.info(
                    "MetaAgent initialized from LogicRegistry with %d pattern groups (%d patterns)",
                    len(self._compiled_patterns),
                    total_patterns,
                )
                return  # Successfully loaded from registry

        # Use hardcoded patterns (backward compatibility or registry fallback)
        self._compiled_patterns = {
            "emergency": [(re.compile(p, re.IGNORECASE), c) for p, c in EMERGENCY_PATTERNS],
            "instant": [(re.compile(p, re.IGNORECASE), c) for p, c in INSTANT_PATTERNS],
            "gesture": [(re.compile(p, re.IGNORECASE), c) for p, c in GESTURE_PATTERNS],
            "self_improvement": [
                (re.compile(p, re.IGNORECASE), c) for p, c in SELF_IMPROVEMENT_PATTERNS
            ],
            "conversation": [(re.compile(p, re.IGNORECASE), c) for p, c in CONVERSATION_PATTERNS],
            "action": [(re.compile(p, re.IGNORECASE), c) for p, c in ACTION_PATTERNS],
            "memory": [(re.compile(p, re.IGNORECASE), c) for p, c in MEMORY_PATTERNS],
            "query": [(re.compile(p, re.IGNORECASE), c) for p, c in QUERY_PATTERNS],
        }
        logger.info(
            "MetaAgent initialized with hardcoded patterns (%d groups)",
            len(self._compiled_patterns),
        )

    async def reload_patterns(self) -> None:
        """Reload patterns from LogicRegistry (for hot-reload)."""
        if self._logic_registry and self._use_registry:
            for group_name in [
                "emergency",
                "instant",
                "gesture",
                "self_improvement",
                "action",
                "memory",
                "query",
            ]:
                patterns = self._logic_registry.get_patterns_as_tuples(group_name)
                self._compiled_patterns[group_name] = [
                    (re.compile(p, re.IGNORECASE), c) for p, c in patterns
                ]
            logger.info("MetaAgent patterns reloaded from LogicRegistry")

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._compiled_patterns.clear()

    async def handle_input(self, text: str, context: dict | None = None) -> dict[str, Any]:
        """Classify intent and evaluate context for input text.

        Returns a dict with classification result and routing info.
        """
        context = context or {}
        result = await self.classify(text, context)

        return {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "sub_category": result.sub_category,
            "target_agent": result.target_agent,
            "priority": result.priority,
            "context_evaluation": (
                {
                    "emotional_tone": result.context.emotional_tone.value,
                    "urgency_level": result.context.urgency_level.value,
                    "empathy_needed": result.context.empathy_needed,
                    "suggested_response_tone": result.context.suggested_response_tone,
                }
                if result.context
                else None
            ),
            "memory_queries": (
                {
                    "primary_query": result.memory_queries.primary_query,
                    "secondary_queries": result.memory_queries.secondary_queries,
                    "topic_tags": result.memory_queries.topic_tags,
                }
                if result.memory_queries
                else None
            ),
            "processing_time_ms": result.total_processing_time_ms,
        }

    async def classify(
        self, text: str, context: dict | None = None, ha_context: dict | None = None
    ) -> ClassificationResult:
        """Full classification with context evaluation.

        Execution order:
        1. Context & Mood Evaluation (runs FIRST to inform other steps)
        2. Intent Classification & Routing (uses HA context for better device detection)
        3. Memory Query Generation (for non-instant intents)

        Args:
            text: User input text
            context: Request context (speaker, room, etc.)
            ha_context: Home Assistant context (entity names, domains, areas) - lightweight
        """
        start_time = time.perf_counter()
        text = text.strip()
        context = context or {}
        ha_context = ha_context or {}

        # Step 1: Context & Mood Evaluation
        context_eval = None
        if self._config.context_evaluation_enabled:
            context_eval = self._evaluate_context_and_mood(text, context)

        # Step 2: Intent Classification (with HA context for better device detection)
        intent_result = await self._classify_intent(text, context, context_eval, ha_context)

        # Step 3: Memory Query Generation (for non-instant intents)
        memory_queries = None
        if self._config.memory_query_generation_enabled:
            if intent_result.intent not in (IntentCategory.INSTANT, IntentCategory.GESTURE):
                memory_queries = self._generate_memory_queries(text, intent_result.intent, context)

        # Determine target agent and priority
        target_agent = INTENT_TO_AGENT.get(intent_result.intent, "interaction")
        priority = self._calculate_priority(intent_result, context_eval)

        total_time_ms = int((time.perf_counter() - start_time) * 1000)

        result = ClassificationResult(
            intent=intent_result.intent,
            confidence=intent_result.confidence,
            sub_category=intent_result.sub_category,
            context=context_eval,
            memory_queries=memory_queries,
            target_agent=target_agent,
            priority=priority,
            total_processing_time_ms=total_time_ms,
            # Carry over diagnostics fields from intent_result
            classification_method=intent_result.classification_method,
            patterns_checked=intent_result.patterns_checked,
            near_miss_patterns=intent_result.near_miss_patterns,
            failure_diagnosis=intent_result.failure_diagnosis,
            diagnostics_summary=intent_result.diagnostics_summary,
            matched_pattern=intent_result.matched_pattern,
        )

        # Record to health monitor for consistency tracking
        if self._health_monitor:
            try:
                self._health_monitor.record_classification(
                    raw_input=text,
                    intent=result.intent.value,
                    sub_category=result.sub_category,
                    confidence=result.confidence,
                    classification_method=result.classification_method or "unknown",
                    matched_pattern=result.matched_pattern,
                    near_misses=None,  # Could extract from diagnostics_summary
                    failure_reason=result.failure_diagnosis,
                )
            except Exception as e:
                logger.debug("Failed to record classification to health monitor: %s", e)

        return result

    def _evaluate_context_and_mood(self, text: str, context: dict) -> ContextEvaluation:
        """Evaluate emotional tone, urgency, and empathy needs."""
        start_time = time.perf_counter()
        text_lower = text.lower()

        # Detect urgency
        urgency_level = UrgencyLevel.LOW
        urgency_matches = [w for w in self._config.urgency_keywords if w in text_lower]
        if urgency_matches:
            urgency_level = UrgencyLevel.HIGH if len(urgency_matches) > 1 else UrgencyLevel.MEDIUM

        # Check for emergency keywords
        for pattern, _ in self._compiled_patterns.get("emergency", []):
            if pattern.search(text):
                urgency_level = UrgencyLevel.EMERGENCY
                break

        # Detect stress indicators
        stress_matches = [w for w in self._config.stress_indicators if w in text_lower]

        # Determine emotional tone
        emotional_tone = EmotionalTone.NEUTRAL
        if stress_matches:
            emotional_tone = EmotionalTone.STRESSED
        elif urgency_level == UrgencyLevel.EMERGENCY:
            emotional_tone = EmotionalTone.URGENT
        elif "?" in text and any(w in text_lower for w in ["what", "how", "why", "confused"]):
            emotional_tone = EmotionalTone.CONFUSED
        elif any(w in text_lower for w in ["thank", "great", "awesome", "love", "happy"]):
            emotional_tone = EmotionalTone.POSITIVE
        elif any(w in text_lower for w in ["hate", "annoying", "bad", "wrong", "terrible"]):
            emotional_tone = EmotionalTone.NEGATIVE

        # Determine if empathy is needed
        empathy_needed = (
            emotional_tone in (EmotionalTone.STRESSED, EmotionalTone.NEGATIVE)
            or len(stress_matches) > 0
        )

        # Suggest response tone based on evaluation
        tone_map = {
            EmotionalTone.STRESSED: "calm_supportive",
            EmotionalTone.NEGATIVE: "empathetic",
            EmotionalTone.POSITIVE: "warm_enthusiastic",
            EmotionalTone.CONFUSED: "patient_clear",
            EmotionalTone.URGENT: "efficient_calm",
            EmotionalTone.NEUTRAL: "friendly",
        }
        suggested_tone = tone_map.get(emotional_tone, "friendly")

        eval_time_ms = int((time.perf_counter() - start_time) * 1000)

        return ContextEvaluation(
            emotional_tone=emotional_tone,
            urgency_level=urgency_level,
            empathy_needed=empathy_needed,
            detected_emotions=[emotional_tone.value],
            stress_indicators=stress_matches,
            suggested_response_tone=suggested_tone,
            confidence=0.8 if stress_matches or urgency_matches else 0.6,
            evaluation_time_ms=eval_time_ms,
        )

    async def _classify_intent(
        self,
        text: str,
        context: dict,
        context_eval: ContextEvaluation | None = None,
        ha_context: dict | None = None,
    ) -> ClassificationResult:
        """Classify intent using tiered approach: pattern → heuristic → LLM.

        Uses HA context (entity names, domains) to improve device detection.
        """
        ha_context = ha_context or {}

        # Phase 1: Pattern matching (fast path)
        result = self._pattern_match(text)
        if result.confidence >= self._config.pattern_match_confidence_threshold:
            logger.debug("Pattern match: %s (conf=%.2f)", result.intent.value, result.confidence)
            return result

        # Phase 2: Heuristic classification (with HA context for device detection)
        result = self._heuristic_classify(text, context, context_eval, ha_context)
        if result.confidence >= self._config.heuristic_confidence_threshold:
            logger.debug("Heuristic match: %s (conf=%.2f)", result.intent.value, result.confidence)
            return result

        # Phase 3: LLM fallback (if available) - includes HA context
        if self._llm_client:
            result = await self._llm_classify(text, context, ha_context)
            result.classification_method = "llm"
            logger.debug(
                "LLM classification: %s (conf=%.2f)", result.intent.value, result.confidence
            )
            return result

        # Return heuristic result if no LLM
        logger.debug(
            "Using heuristic result: %s (conf=%.2f)", result.intent.value, result.confidence
        )
        return result

    def _pattern_match(self, text: str) -> ClassificationResult:
        """Pattern-based classification with priority ordering and diagnostics.

        Now includes full diagnostic information about:
        - How many patterns were checked
        - Which patterns almost matched (near misses)
        - Why patterns failed to match
        """
        # Run diagnostics if available
        diag = None
        if self._diagnostics_service:
            diag = self._diagnostics_service.diagnose_pattern_match(
                text=text,
                compiled_patterns=self._compiled_patterns,
                pattern_priority=self.PATTERN_PRIORITY,
            )

        # Count patterns for result
        total_patterns = sum(len(p) for p in self._compiled_patterns.values())

        # Check patterns in priority order
        for pattern_group, intent, confidence in self.PATTERN_PRIORITY:
            patterns = self._compiled_patterns.get(pattern_group, [])
            for pattern, sub_category in patterns:
                if pattern.match(text):
                    result = ClassificationResult(
                        intent=intent,
                        confidence=confidence,
                        sub_category=sub_category,
                        matched_pattern=f"{pattern_group}:{sub_category or 'default'} → {pattern.pattern}",
                        classification_method="pattern",
                        patterns_checked=total_patterns,
                    )
                    if diag:
                        result.diagnostics_summary = {
                            "processing_time_ms": diag.processing_time_ms,
                            "total_checked": diag.total_patterns_checked,
                        }
                    return result

        # No match - include diagnostic info about what almost worked
        result = ClassificationResult(
            intent=IntentCategory.UNKNOWN,
            confidence=0.0,
            classification_method="pattern_failed",
            patterns_checked=total_patterns,
        )

        if diag:
            # Add near-miss information
            result.near_miss_patterns = [
                f"{nm.pattern_group}:{nm.sub_category} (sim={nm.similarity_score:.2f})"
                for nm in diag.near_misses[:5]
            ]
            if diag.near_misses:
                top_miss = diag.near_misses[0]
                if top_miss.failure_reason:
                    result.failure_diagnosis = top_miss.failure_reason.value
            result.diagnostics_summary = {
                "processing_time_ms": diag.processing_time_ms,
                "total_checked": diag.total_patterns_checked,
                "near_misses": len(diag.near_misses),
                "suggested_patterns": diag.suggested_patterns[:3],
                "suggested_modifications": diag.suggested_modifications[:3],
            }

        return result

    def _heuristic_classify(
        self,
        text: str,
        context: dict,
        context_eval: ContextEvaluation | None = None,
        ha_context: dict | None = None,
    ) -> ClassificationResult:
        """Heuristic-based classification with context awareness and HA entity detection."""
        text_lower = text.lower()
        ha_context = ha_context or {}

        # Check for conversation continuation
        if context.get("history") and len(context["history"]) > 0:
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.75,
                matched_pattern="heuristic:conversation_history → has prior conversation context",
                classification_method="heuristic",
            )

        # Urgency from context evaluation influences classification
        if context_eval and context_eval.urgency_level == UrgencyLevel.EMERGENCY:
            return ClassificationResult(
                intent=IntentCategory.EMERGENCY,
                confidence=0.85,
                matched_pattern="heuristic:urgency → context evaluated as EMERGENCY",
                classification_method="heuristic",
            )

        # Check if text mentions HA entities (device detection)
        entity_names = ha_context.get("entity_names", [])
        if entity_names:
            # Check if any entity name is mentioned in the text
            mentioned_entities = [
                name for name in entity_names if name.lower() in text_lower
            ]
            if mentioned_entities:
                # If entity mentioned + command verb = ACTION
                command_verbs = {
                    "turn", "set", "change", "make", "adjust", "open", "close",
                    "start", "stop", "play", "pause", "lock", "unlock", "activate",
                }
                words = text_lower.split()
                has_command = any(word in command_verbs for word in words[:3])

                if has_command:
                    return ClassificationResult(
                        intent=IntentCategory.ACTION,
                        confidence=0.85,  # Higher confidence with entity match
                        matched_pattern=f"heuristic:entity_command → mentions '{mentioned_entities[0]}' + command verb",
                        classification_method="heuristic",
                    )
                else:
                    # Entity mentioned but no command = QUERY (asking about device)
                    return ClassificationResult(
                        intent=IntentCategory.QUERY,
                        confidence=0.80,
                        matched_pattern=f"heuristic:entity_query → mentions '{mentioned_entities[0]}' (asking about device)",
                        classification_method="heuristic",
                    )

        # Question markers
        question_starters = (
            "what",
            "where",
            "when",
            "who",
            "how",
            "why",
            "is",
            "are",
            "can",
            "could",
        )
        if text.endswith("?") or text_lower.startswith(question_starters):
            return ClassificationResult(
                intent=IntentCategory.QUERY,
                confidence=0.70,
                matched_pattern="heuristic:question → ends with '?' or starts with question word",
                classification_method="heuristic",
            )

        # Command verbs
        command_verbs = {
            "turn",
            "set",
            "change",
            "make",
            "adjust",
            "open",
            "close",
            "start",
            "stop",
            "play",
            "pause",
            "lock",
            "unlock",
            "activate",
        }
        words = text_lower.split()
        first_word = words[0] if words else ""
        if first_word in command_verbs:
            return ClassificationResult(
                intent=IntentCategory.ACTION,
                confidence=0.70,
                matched_pattern=f"heuristic:command → starts with verb '{first_word}'",
                classification_method="heuristic",
            )

        # Default to conversation
        return ClassificationResult(
            intent=IntentCategory.CONVERSATION,
            confidence=0.50,
            matched_pattern="heuristic:default → no patterns matched, assuming conversation",
            classification_method="heuristic",
        )

    async def _llm_classify(
        self, text: str, context: dict, ha_context: dict | None = None
    ) -> ClassificationResult:
        """Use LLM for classification when pattern/heuristic fails."""
        if not self._llm_client:
            return ClassificationResult(
                intent=IntentCategory.UNKNOWN,
                confidence=0.0,
            )

        system_prompt = """You are an intent classifier for a smart home assistant.
Classify the user's request into one of these categories:
- instant: Simple queries (time, date, greetings, basic math)
- action: Device control (turn on/off, set temperature, lock doors)
- query: Information requests (weather, sensor states, complex questions)
- conversation: General chat, advice, complex dialogue
- memory: Remember or recall information
- emergency: Safety concerns (fire, medical, security)

Respond with JSON: {"intent": "<category>", "confidence": 0.0-1.0, "sub_category": "optional detail"}"""

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Classify: {text}"},
                ],
                agent_type="meta",
                user_input=text,
            )

            # Parse JSON response
            import json

            result = json.loads(response.text)
            intent_str = result.get("intent", "unknown")
            intent = (
                IntentCategory(intent_str)
                if intent_str in [e.value for e in IntentCategory]
                else IntentCategory.UNKNOWN
            )

            return ClassificationResult(
                intent=intent,
                confidence=result.get("confidence", 0.7),
                sub_category=result.get("sub_category"),
            )
        except Exception as e:
            logger.warning("LLM classification failed: %s", e)
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.5,
            )

    def _generate_memory_queries(
        self, text: str, intent: IntentCategory, context: dict
    ) -> MemoryQuerySet:
        """Generate memory search queries based on intent and text."""
        start_time = time.perf_counter()

        # Extract potential topics from text
        # Simple word extraction - could be enhanced with NLP
        words = text.lower().split()
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "i",
            "you",
            "we",
            "they",
            "he",
            "she",
            "it",
            "what",
            "when",
            "where",
            "how",
            "why",
        }
        topic_words = [w for w in words if w not in stop_words and len(w) > 2]

        # Generate primary query
        primary_query = text

        # Generate secondary queries based on intent
        secondary_queries: list[str] = []
        if intent == IntentCategory.MEMORY:
            secondary_queries = [f"previous mentions of {w}" for w in topic_words[:2]]
        elif intent == IntentCategory.CONVERSATION:
            secondary_queries = [f"conversations about {w}" for w in topic_words[:2]]
        elif intent == IntentCategory.ACTION:
            secondary_queries = [f"device preferences for {w}" for w in topic_words[:2]]

        # Extract relevant people from context
        relevant_people = context.get("family_members", [])
        speaker = context.get("speaker")
        if speaker and speaker not in relevant_people:
            relevant_people = [speaker] + relevant_people

        # Determine time context
        time_context = None
        if "today" in text.lower() or "now" in text.lower():
            time_context = "recent"
        elif "yesterday" in text.lower():
            time_context = "last_day"
        elif "week" in text.lower():
            time_context = "last_week"

        gen_time_ms = int((time.perf_counter() - start_time) * 1000)

        return MemoryQuerySet(
            primary_query=primary_query,
            secondary_queries=secondary_queries[: self._config.max_secondary_queries],
            topic_tags=topic_words[:5],
            relevant_people=relevant_people[:3],
            time_context=time_context,
            memory_types=["preference", "event", "conversation"],
            confidence=0.7,
            generation_time_ms=gen_time_ms,
        )

    def _calculate_priority(
        self, classification: ClassificationResult, context_eval: ContextEvaluation | None
    ) -> int:
        """Calculate request priority (1-10, higher = more urgent)."""
        # Base priority by intent
        intent_priority = {
            IntentCategory.EMERGENCY: 10,
            IntentCategory.ACTION: 7,
            IntentCategory.INSTANT: 6,
            IntentCategory.QUERY: 5,
            IntentCategory.CONVERSATION: 4,
            IntentCategory.MEMORY: 3,
            IntentCategory.GESTURE: 6,
            IntentCategory.UNKNOWN: 5,
        }
        priority = intent_priority.get(classification.intent, 5)

        # Adjust based on urgency level
        if context_eval:
            urgency_boost = {
                UrgencyLevel.EMERGENCY: 3,
                UrgencyLevel.HIGH: 2,
                UrgencyLevel.MEDIUM: 1,
                UrgencyLevel.LOW: 0,
            }
            priority += urgency_boost.get(context_eval.urgency_level, 0)

        return min(10, max(1, priority))


__all__ = [
    "MetaAgent",
    "MetaAgentConfig",
    "IntentCategory",
    "UrgencyLevel",
    "EmotionalTone",
    "ContextEvaluation",
    "MemoryQuerySet",
    "ClassificationResult",
]
