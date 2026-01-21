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
    (r"^(what('s| is) (the )?)?(current )?time(\?)?$", "time"),
    (r"^what time is it(\?)?$", "time"),
    (r"^(what('s| is) (the )?)?(today'?s? )?date(\?)?$", "date"),
    (r"^(hello|hey|hi)( barnabee)?(\?)?$", "greeting"),
    (r"^good (morning|afternoon|evening|night)$", "greeting"),
    (r"^(what('s| is) )?(\d+)\s*[\+\-\*\/]\s*(\d+)(\?)?$", "math"),
    (r"^(how are you|you okay)(\?)?$", "status"),
    (r"^thank(s| you).*$", "thanks"),
    # Mic check / test queries
    (r"^(can you hear me|do you hear me|are you there|testing)(\?)?$", "mic_check"),
    (r"^test(ing)?( 1 2 3)?(\?)?$", "mic_check"),
    (r"^(is this|this is|am i) (working|on)(\?)?$", "mic_check"),
]

ACTION_PATTERNS: list[tuple[str, str]] = [
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
    (r"^(play|pause|stop|skip) .*$", "media"),
    (r"^activate .*$", "scene"),
    (r"^(start|stop) .* mode$", "mode"),
]

QUERY_PATTERNS: list[tuple[str, str]] = [
    (r"^(what('s| is) the )?(temperature|weather|humidity) .*$", "sensor"),
    (r"^(is|are) .* (on|off|open|closed|locked|unlocked)(\?)?$", "state"),
    (r"^(what|how much|how many) .*$", "query"),
    (r"^(when|where) .*$", "query"),
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
                "action",
                "memory",
                "query",
            ]:
                patterns = self._logic_registry.get_patterns_as_tuples(group_name)
                self._compiled_patterns[group_name] = [
                    (re.compile(p, re.IGNORECASE), c) for p, c in patterns
                ]
            logger.info(
                "MetaAgent initialized from LogicRegistry with %d pattern groups",
                len(self._compiled_patterns),
            )
        else:
            # Use hardcoded patterns (backward compatibility)
            self._compiled_patterns = {
                "emergency": [(re.compile(p, re.IGNORECASE), c) for p, c in EMERGENCY_PATTERNS],
                "instant": [(re.compile(p, re.IGNORECASE), c) for p, c in INSTANT_PATTERNS],
                "gesture": [(re.compile(p, re.IGNORECASE), c) for p, c in GESTURE_PATTERNS],
                "self_improvement": [
                    (re.compile(p, re.IGNORECASE), c) for p, c in SELF_IMPROVEMENT_PATTERNS
                ],
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
