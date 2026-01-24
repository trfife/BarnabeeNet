# BarnabeeNet Meta Agent Specification

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Purpose:** Detailed specification for the enhanced Meta Agent with four responsibilities  
**Related Documents:** BarnabeeNet_Technical_Architecture.md, SkyrimNet_Deep_Research_For_BarnabeeNet.md

---

## Overview

This document expands the Meta Agent specification from a simple router to a cognitive pre-processor with **four distinct responsibilities**, based on patterns observed in SkyrimNet's Meta Evaluation model.

### The Four Responsibilities

| # | Responsibility | Purpose | Execution Order |
|---|----------------|---------|-----------------|
| 1 | Intent Classification & Routing | Determine request type and target agent | After context evaluation |
| 2 | Context & Mood Evaluation | Analyze emotional tone, urgency, empathy needs | **FIRST** (informs all other steps) |
| 3 | Memory Query Generation | Generate semantic search queries for memory retrieval | After classification |
| 4 | Deferred Proactive Evaluation | Gate proactive suggestions until interaction queue is empty | Continuous background |

**Key Insight from SkyrimNet:** The Meta model serves as the cognitive pre-processor—it evaluates context and prepares all downstream agents with the information they need *before* any specialized processing begins. This "evaluate first, route second" pattern is what makes interactions feel contextually appropriate.

---

## Table of Contents

1. [Data Structures](#data-structures)
2. [Configuration Parameters](#configuration-parameters)
3. [Enhanced MetaAgent Class](#enhanced-metaagent-class)
4. [Responsibility 1: Intent Classification & Routing](#responsibility-1-intent-classification--routing)
5. [Responsibility 2: Context & Mood Evaluation](#responsibility-2-context--mood-evaluation)
6. [Responsibility 3: Memory Query Generation](#responsibility-3-memory-query-generation)
7. [Responsibility 4: Deferred Proactive Evaluation](#responsibility-4-deferred-proactive-evaluation)
8. [Prompt Templates](#prompt-templates)
9. [Integration Patterns](#integration-patterns)

---

## Data Structures

### Core Enums

```python
# agents/meta_agent.py
"""Meta Agent - Request classification, context evaluation, memory query generation."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from ..core.bus import MessageBus
    from ..core.policy import PolicyEngine
    from ..memory import MemoryManager

_LOGGER = logging.getLogger(__name__)


class IntentCategory(Enum):
    """Intent classification categories."""
    INSTANT = "instant"
    ACTION = "action"
    QUERY = "query"
    CONVERSATION = "conversation"
    MEMORY = "memory"
    EMERGENCY = "emergency"
    PROACTIVE = "proactive"
    GESTURE = "gesture"
    UNKNOWN = "unknown"


class UrgencyLevel(Enum):
    """Urgency classification for requests."""
    LOW = "low"           # Normal conversation, can wait
    MEDIUM = "medium"     # Time-sensitive but not critical
    HIGH = "high"         # Requires immediate attention
    EMERGENCY = "emergency"  # Safety-critical, interrupt everything


class EmotionalTone(Enum):
    """Detected emotional tone of requests."""
    NEUTRAL = "neutral"
    POSITIVE = "positive"      # Happy, excited, grateful
    NEGATIVE = "negative"      # Frustrated, sad, worried
    STRESSED = "stressed"      # Overwhelmed, anxious
    CONFUSED = "confused"      # Needs clarification
    URGENT = "urgent"          # Demanding immediate action
```

### Result Data Classes

```python
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
    primary_query: str                           # Main semantic search query
    secondary_queries: list[str] = field(default_factory=list)  # Alternative/related queries
    topic_tags: list[str] = field(default_factory=list)         # For tag-based filtering
    relevant_people: list[str] = field(default_factory=list)    # Family members involved
    time_context: Optional[str] = None           # "recent", "last_week", "morning_routine", etc.
    memory_types: list[str] = field(default_factory=list)       # routine, preference, event, etc.
    confidence: float = 0.0
    generation_time_ms: int = 0


@dataclass
class ClassificationResult:
    """Complete result from Meta Agent processing."""
    # Intent classification (existing)
    intent: IntentCategory
    confidence: float
    sub_category: Optional[str] = None
    
    # Context evaluation (NEW)
    context: Optional[ContextEvaluation] = None
    
    # Memory queries (NEW)
    memory_queries: Optional[MemoryQuerySet] = None
    
    # Routing metadata
    target_agent: Optional[str] = None
    priority: int = 5  # 1-10, higher = more urgent
    
    # Timing
    total_processing_time_ms: int = 0


@dataclass
class ProactiveCandidate:
    """A queued proactive suggestion awaiting delivery."""
    suggestion_id: str
    content: str
    trigger_source: str
    priority: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    target_room: Optional[str] = None
    target_person: Optional[str] = None
    requires_acknowledgment: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class InteractionState:
    """Current state of the interaction queue."""
    pending_requests: int = 0
    active_conversations: int = 0
    last_user_interaction: Optional[datetime] = None
    last_barnabee_speech: Optional[datetime] = None
    current_speaker: Optional[str] = None
    conversation_depth: int = 0  # Turns in current conversation
```

---

## Configuration Parameters

```python
@dataclass
class MetaAgentConfig:
    """Configuration for Meta Agent behavior."""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT CLASSIFICATION
    # ═══════════════════════════════════════════════════════════════════════════
    pattern_match_confidence_threshold: float = 0.9
    heuristic_confidence_threshold: float = 0.7
    llm_classification_timeout_ms: int = 500
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT EVALUATION
    # ═══════════════════════════════════════════════════════════════════════════
    context_evaluation_enabled: bool = True
    empathy_detection_sensitivity: float = 0.6
    urgency_keywords: list[str] = field(default_factory=lambda: [
        "emergency", "urgent", "help", "now", "immediately", "quick",
        "asap", "hurry", "critical", "important"
    ])
    stress_indicators: list[str] = field(default_factory=lambda: [
        "frustrated", "annoyed", "tired", "exhausted", "overwhelmed",
        "stressed", "worried", "anxious", "upset"
    ])
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEMORY QUERY GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    memory_query_generation_enabled: bool = True
    max_secondary_queries: int = 3
    memory_query_timeout_ms: int = 300
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEFERRED PROACTIVE EVALUATION
    # ═══════════════════════════════════════════════════════════════════════════
    proactive_evaluation_enabled: bool = True
    proactive_queue_max_size: int = 10
    proactive_min_silence_seconds: float = 5.0  # Minimum silence before proactive
    proactive_conversation_cooldown_seconds: float = 30.0  # Wait after conversation ends
    proactive_max_pending_interactions: int = 0  # Default: no pending allowed
    proactive_suggestion_ttl_seconds: float = 300.0  # 5 minutes default
    proactive_priority_threshold: int = 7  # Only deliver priority >= this when busy
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LLM CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════
    meta_llm_model: str = "deepseek/deepseek-v3"  # Fast, cheap for high-frequency
    meta_llm_temperature: float = 0.5
    meta_llm_max_tokens: int = 200
```

### YAML Configuration Example

```yaml
# config/meta_agent.yaml
meta_agent:
  # Intent Classification
  pattern_match_confidence_threshold: 0.9
  heuristic_confidence_threshold: 0.7
  llm_classification_timeout_ms: 500
  
  # Context Evaluation
  context_evaluation_enabled: true
  empathy_detection_sensitivity: 0.6
  urgency_keywords:
    - emergency
    - urgent
    - help
    - now
    - immediately
    - quick
    - asap
    - hurry
    - critical
    - important
  stress_indicators:
    - frustrated
    - annoyed
    - tired
    - exhausted
    - overwhelmed
    - stressed
    - worried
    - anxious
    - upset
  
  # Memory Query Generation
  memory_query_generation_enabled: true
  max_secondary_queries: 3
  memory_query_timeout_ms: 300
  
  # Deferred Proactive Evaluation
  proactive_evaluation_enabled: true
  proactive_queue_max_size: 10
  proactive_min_silence_seconds: 5.0
  proactive_conversation_cooldown_seconds: 30.0
  proactive_max_pending_interactions: 0
  proactive_suggestion_ttl_seconds: 300.0
  proactive_priority_threshold: 7
  
  # LLM Configuration
  meta_llm_model: "deepseek/deepseek-v3"
  meta_llm_temperature: 0.5
  meta_llm_max_tokens: 200
```

---

## Enhanced MetaAgent Class

```python
class MetaAgent(BaseAgent):
    """
    Meta Agent with four responsibilities:
    1. Intent Classification & Routing
    2. Context & Mood Evaluation
    3. Memory Query Generation
    4. Deferred Proactive Evaluation
    """
    
    agent_type = AgentType.META
    latency_target_ms = 50  # Increased slightly for additional responsibilities
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATTERN DEFINITIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    INSTANT_PATTERNS = [
        (r"^(what('s| is) the )?(current )?time(\?)?$", "time"),
        (r"^(what('s| is) )?(today'?s? )?date(\?)?$", "date"),
        (r"^(hello|hey|hi)( barnabee)?(\?)?$", "greeting"),
        (r"^good (morning|afternoon|evening|night)$", "greeting"),
        (r"^(what('s| is) )?(\d+)\s*[\+\-\*\/]\s*(\d+)(\?)?$", "math"),
        (r"^(how are you|you okay)(\?)?$", "status"),
        (r"^thank(s| you).*$", "thanks"),
    ]
    
    ACTION_PATTERNS = [
        (r"^(turn|switch) (on|off) .*$", "switch"),
        (r"^(set|change) .* to .*$", "set"),
        (r"^(dim|brighten) .*$", "light"),
        (r"^(lock|unlock) .*$", "lock"),
        (r"^(open|close) .*$", "cover"),
        (r"^(play|pause|stop|skip) .*$", "media"),
        (r"^activate .*$", "scene"),
        (r"^(start|stop) .* mode$", "mode"),
    ]
    
    QUERY_PATTERNS = [
        (r"^(what('s| is) the )?(temperature|weather|humidity) .*$", "sensor"),
        (r"^(is|are) .* (on|off|open|closed|locked|unlocked)(\?)?$", "state"),
        (r"^(what|how much|how many) .*$", "query"),
        (r"^(when|where) .*$", "query"),
    ]
    
    MEMORY_PATTERNS = [
        (r"^remember (that )?.*$", "store"),
        (r"^(do you remember|what do you know about) .*$", "recall"),
        (r"^forget .*$", "forget"),
        (r"^(when|what) did (i|we) .*$", "recall"),
    ]
    
    GESTURE_PATTERNS = [
        (r"^crown_twist_(yes|no|up|down)$", "choice"),
        (r"^button_click_(confirm|cancel)$", "confirm"),
        (r"^motion_shake$", "dismiss"),
        (r"^double_tap$", "quick_action"),
    ]
    
    # Emergency patterns (NEW - highest priority)
    EMERGENCY_PATTERNS = [
        (r".*(fire|smoke|burning|flames).*", "fire"),
        (r".*(help|emergency|911|ambulance).*", "emergency"),
        (r".*(intruder|break.?in|someone.?in.?the.?house).*", "security"),
        (r".*(fall|fallen|can'?t get up|hurt).*", "medical"),
    ]
    
    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        bus: MessageBus,
        policy: PolicyEngine,
        memory: MemoryManager,
        meta_config: Optional[MetaAgentConfig] = None,
    ) -> None:
        """Initialize Meta Agent with configuration."""
        super().__init__(hass, config, bus, policy, memory)
        self.meta_config = meta_config or MetaAgentConfig()
        
        # Proactive suggestion queue
        self._proactive_queue: list[ProactiveCandidate] = []
        self._proactive_lock = asyncio.Lock()
        
        # Interaction state tracking
        self._interaction_state = InteractionState()
        self._state_lock = asyncio.Lock()
        
        # Compiled patterns (populated in _async_setup)
        self._compiled_patterns: dict[str, list[tuple]] = {}
    
    async def _async_setup(self) -> None:
        """Setup Meta Agent - compile patterns and start monitors."""
        # Compile all pattern groups
        self._compiled_patterns = {
            "emergency": [(re.compile(p, re.IGNORECASE), c) for p, c in self.EMERGENCY_PATTERNS],
            "instant": [(re.compile(p, re.IGNORECASE), c) for p, c in self.INSTANT_PATTERNS],
            "gesture": [(re.compile(p, re.IGNORECASE), c) for p, c in self.GESTURE_PATTERNS],
            "action": [(re.compile(p, re.IGNORECASE), c) for p, c in self.ACTION_PATTERNS],
            "memory": [(re.compile(p, re.IGNORECASE), c) for p, c in self.MEMORY_PATTERNS],
            "query": [(re.compile(p, re.IGNORECASE), c) for p, c in self.QUERY_PATTERNS],
        }
        
        # Subscribe to interaction events for state tracking
        await self.bus.subscribe(
            "interaction_started",
            self._handle_interaction_started
        )
        await self.bus.subscribe(
            "interaction_completed",
            self._handle_interaction_completed
        )
        
        _LOGGER.info("MetaAgent initialized with enhanced capabilities")
```

---

## Responsibility 1: Intent Classification & Routing

### Main Processing Entry Point

```python
    async def async_full_evaluation(
        self,
        request: AgentRequest
    ) -> ClassificationResult:
        """
        Complete Meta Agent evaluation with all four responsibilities.
        
        Execution order:
        1. Context & Mood Evaluation (runs FIRST to inform other steps)
        2. Intent Classification & Routing
        3. Memory Query Generation
        4. Update interaction state (for proactive gating)
        """
        start_time = time.perf_counter()
        text = request.text.strip()
        
        # ─────────────────────────────────────────────────────────────────────
        # STEP 1: Context & Mood Evaluation (runs BEFORE routing)
        # ─────────────────────────────────────────────────────────────────────
        context_eval = None
        if self.meta_config.context_evaluation_enabled:
            context_eval = await self._evaluate_context_and_mood(
                text=text,
                speaker_id=request.speaker_id,
                context=request.context,
            )
        
        # ─────────────────────────────────────────────────────────────────────
        # STEP 2: Intent Classification & Routing
        # ─────────────────────────────────────────────────────────────────────
        classification = await self._classify_intent(
            text=text,
            context=request.context,
            context_eval=context_eval,
        )
        
        # ─────────────────────────────────────────────────────────────────────
        # STEP 3: Memory Query Generation
        # ─────────────────────────────────────────────────────────────────────
        memory_queries = None
        if self.meta_config.memory_query_generation_enabled:
            # Generate memory queries for non-instant intents
            if classification.intent not in (IntentCategory.INSTANT, IntentCategory.GESTURE):
                memory_queries = await self._generate_memory_queries(
                    text=text,
                    intent=classification.intent,
                    speaker_id=request.speaker_id,
                    context=request.context,
                )
        
        # ─────────────────────────────────────────────────────────────────────
        # STEP 4: Update Interaction State
        # ─────────────────────────────────────────────────────────────────────
        await self._update_interaction_state(request)
        
        # ─────────────────────────────────────────────────────────────────────
        # Assemble final result
        # ─────────────────────────────────────────────────────────────────────
        total_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        return ClassificationResult(
            intent=classification.intent,
            confidence=classification.confidence,
            sub_category=classification.sub_category,
            context=context_eval,
            memory_queries=memory_queries,
            target_agent=self._determine_target_agent(classification.intent),
            priority=self._calculate_priority(classification, context_eval),
            total_processing_time_ms=total_time_ms,
        )
```

### Tiered Classification Approach

```python
    async def _classify_intent(
        self,
        text: str,
        context: dict,
        context_eval: Optional[ContextEvaluation] = None,
    ) -> ClassificationResult:
        """
        Classify the intent of a request using tiered approach:
        Phase 1: Pattern matching (fast path)
        Phase 2: Heuristic classification
        Phase 3: LLM fallback
        """
        # Phase 1: Pattern matching
        result = self._pattern_match(text)
        if result.confidence >= self.meta_config.pattern_match_confidence_threshold:
            _LOGGER.debug(f"Pattern match: {result.intent.value} (conf={result.confidence})")
            return result
        
        # Phase 2: Heuristic classification
        result = self._heuristic_classify(text, context, context_eval)
        if result.confidence >= self.meta_config.heuristic_confidence_threshold:
            _LOGGER.debug(f"Heuristic match: {result.intent.value} (conf={result.confidence})")
            return result
        
        # Phase 3: LLM fallback
        result = await self._llm_classify(text, context)
        _LOGGER.debug(f"LLM classification: {result.intent.value} (conf={result.confidence})")
        return result
    
    def _pattern_match(self, text: str) -> ClassificationResult:
        """Pattern-based classification with priority ordering."""
        
        # Check patterns in priority order
        pattern_priority = [
            ("emergency", IntentCategory.EMERGENCY, 0.99),
            ("instant", IntentCategory.INSTANT, 0.95),
            ("gesture", IntentCategory.GESTURE, 0.95),
            ("action", IntentCategory.ACTION, 0.90),
            ("memory", IntentCategory.MEMORY, 0.90),
            ("query", IntentCategory.QUERY, 0.85),
        ]
        
        for pattern_group, intent, confidence in pattern_priority:
            patterns = self._compiled_patterns.get(pattern_group, [])
            for pattern, sub_category in patterns:
                if pattern.match(text):
                    return ClassificationResult(
                        intent=intent,
                        confidence=confidence,
                        sub_category=sub_category,
                    )
        
        return ClassificationResult(
            intent=IntentCategory.UNKNOWN,
            confidence=0.0,
        )
    
    def _heuristic_classify(
        self,
        text: str,
        context: dict,
        context_eval: Optional[ContextEvaluation] = None,
    ) -> ClassificationResult:
        """Heuristic-based classification with context awareness."""
        text_lower = text.lower()
        
        # Check for conversation continuation
        if context.get("history") and len(context["history"]) > 0:
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.75,
            )
        
        # Urgency from context evaluation influences classification
        if context_eval and context_eval.urgency_level == UrgencyLevel.EMERGENCY:
            return ClassificationResult(
                intent=IntentCategory.EMERGENCY,
                confidence=0.85,
            )
        
        # Question markers
        if text.endswith("?") or text_lower.startswith((
            "what", "where", "when", "who", "how", "why", "is", "are", "can", "could"
        )):
            return ClassificationResult(
                intent=IntentCategory.QUERY,
                confidence=0.70,
            )
        
        # Command verbs
        command_verbs = [
            "turn", "set", "change", "make", "adjust", "open", "close",
            "start", "stop", "play", "pause", "lock", "unlock", "activate"
        ]
        first_word = text_lower.split()[0] if text_lower.split() else ""
        if first_word in command_verbs:
            return ClassificationResult(
                intent=IntentCategory.ACTION,
                confidence=0.70,
            )
        
        # Default to conversation
        return ClassificationResult(
            intent=IntentCategory.CONVERSATION,
            confidence=0.50,
        )
    
    async def _llm_classify(
        self,
        text: str,
        context: dict,
    ) -> ClassificationResult:
        """LLM-based classification for ambiguous cases."""
        from ..llm import LLMRouter
        
        prompt = self._get_classification_prompt(text, context)
        
        try:
            llm = LLMRouter(self.hass, self.config)
            response = await asyncio.wait_for(
                llm.async_complete(
                    prompt=prompt,
                    model=self.meta_config.meta_llm_model,
                    max_tokens=self.meta_config.meta_llm_max_tokens,
                    temperature=self.meta_config.meta_llm_temperature,
                ),
                timeout=self.meta_config.llm_classification_timeout_ms / 1000,
            )
            
            # Parse response
            parts = response.strip().split(",")
            category = parts[0].strip().lower()
            confidence = float(parts[1].strip()) if len(parts) > 1 else 0.7
            
            category_map = {
                "instant": IntentCategory.INSTANT,
                "action": IntentCategory.ACTION,
                "query": IntentCategory.QUERY,
                "conversation": IntentCategory.CONVERSATION,
                "memory": IntentCategory.MEMORY,
                "emergency": IntentCategory.EMERGENCY,
            }
            
            return ClassificationResult(
                intent=category_map.get(category, IntentCategory.CONVERSATION),
                confidence=confidence,
            )
            
        except asyncio.TimeoutError:
            _LOGGER.warning("LLM classification timeout")
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.50,
            )
        except Exception as e:
            _LOGGER.warning(f"LLM classification failed: {e}")
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.50,
            )
```

---

## Responsibility 2: Context & Mood Evaluation

This evaluation runs **BEFORE** routing to inform how the response should be delivered.

```python
    async def _evaluate_context_and_mood(
        self,
        text: str,
        speaker_id: str,
        context: dict,
    ) -> ContextEvaluation:
        """
        Analyze emotional tone, urgency, and empathy needs.
        Runs BEFORE routing to inform how the response should be delivered.
        """
        start_time = time.perf_counter()
        text_lower = text.lower()
        
        # ─────────────────────────────────────────────────────────────────────
        # Fast-path heuristic evaluation
        # ─────────────────────────────────────────────────────────────────────
        
        # Detect urgency
        urgency_level = UrgencyLevel.LOW
        urgency_matches = [
            word for word in self.meta_config.urgency_keywords
            if word in text_lower
        ]
        if urgency_matches:
            if any(w in text_lower for w in ["emergency", "911", "help"]):
                urgency_level = UrgencyLevel.EMERGENCY
            elif any(w in text_lower for w in ["now", "immediately", "asap"]):
                urgency_level = UrgencyLevel.HIGH
            else:
                urgency_level = UrgencyLevel.MEDIUM
        
        # Detect stress indicators
        stress_matches = [
            indicator for indicator in self.meta_config.stress_indicators
            if indicator in text_lower
        ]
        
        # Detect emotional tone
        emotional_tone, detected_emotions = self._detect_emotional_tone(text_lower)
        
        # Determine if empathy is needed
        empathy_needed = (
            emotional_tone in (EmotionalTone.NEGATIVE, EmotionalTone.STRESSED) or
            len(stress_matches) > 0 or
            urgency_level in (UrgencyLevel.HIGH, UrgencyLevel.EMERGENCY)
        )
        
        # Suggest response tone
        if urgency_level == UrgencyLevel.EMERGENCY:
            suggested_tone = "calm_urgent"
        elif empathy_needed:
            suggested_tone = "empathetic"
        elif emotional_tone == EmotionalTone.POSITIVE:
            suggested_tone = "warm"
        else:
            suggested_tone = "friendly"
        
        # Calculate confidence based on signal strength
        signal_count = len(urgency_matches) + len(stress_matches) + len(detected_emotions)
        confidence = min(0.95, 0.5 + (signal_count * 0.15))
        
        eval_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        return ContextEvaluation(
            emotional_tone=emotional_tone,
            urgency_level=urgency_level,
            empathy_needed=empathy_needed,
            detected_emotions=detected_emotions,
            stress_indicators=stress_matches,
            suggested_response_tone=suggested_tone,
            confidence=confidence,
            evaluation_time_ms=eval_time_ms,
        )
    
    def _detect_emotional_tone(
        self,
        text_lower: str
    ) -> tuple[EmotionalTone, list[str]]:
        """Detect emotional tone from text."""
        
        emotion_patterns = {
            EmotionalTone.POSITIVE: [
                "happy", "great", "awesome", "love", "thanks", "wonderful",
                "excited", "amazing", "perfect", "yay", "fantastic"
            ],
            EmotionalTone.NEGATIVE: [
                "hate", "angry", "upset", "annoyed", "frustrated", "terrible",
                "awful", "bad", "wrong", "broken", "stupid"
            ],
            EmotionalTone.STRESSED: [
                "stressed", "overwhelmed", "exhausted", "tired", "anxious",
                "worried", "can't handle", "too much", "busy"
            ],
            EmotionalTone.CONFUSED: [
                "confused", "don't understand", "what do you mean", "huh",
                "unclear", "lost", "not sure"
            ],
            EmotionalTone.URGENT: [
                "hurry", "quick", "fast", "now", "immediately", "asap"
            ],
        }
        
        detected = []
        tone_scores: dict[EmotionalTone, int] = {}
        
        for tone, patterns in emotion_patterns.items():
            matches = [p for p in patterns if p in text_lower]
            if matches:
                tone_scores[tone] = len(matches)
                detected.extend(matches)
        
        if not tone_scores:
            return EmotionalTone.NEUTRAL, []
        
        # Return highest scoring tone
        primary_tone = max(tone_scores.keys(), key=lambda t: tone_scores[t])
        return primary_tone, detected
```

---

## Responsibility 3: Memory Query Generation

The Meta Agent generates semantic search queries that the Memory Agent will execute.

```python
    async def _generate_memory_queries(
        self,
        text: str,
        intent: IntentCategory,
        speaker_id: str,
        context: dict,
    ) -> MemoryQuerySet:
        """
        Generate semantic search queries for memory retrieval.
        The Memory Agent will execute these queries.
        """
        start_time = time.perf_counter()
        
        # Try fast heuristic extraction first
        queries = self._heuristic_query_extraction(text, speaker_id, context)
        
        # If heuristics insufficient, use LLM
        if queries.confidence < 0.6:
            queries = await self._llm_query_generation(text, speaker_id, context)
        
        queries.generation_time_ms = int((time.perf_counter() - start_time) * 1000)
        return queries
    
    def _heuristic_query_extraction(
        self,
        text: str,
        speaker_id: str,
        context: dict,
    ) -> MemoryQuerySet:
        """Fast heuristic-based query extraction."""
        text_lower = text.lower()
        
        # Extract topic keywords (nouns and noun phrases)
        topic_keywords = []
        
        # Common patterns that reference memory
        memory_reference_patterns = [
            (r"what did (?:i|we) (?:say|mention|talk) about (.+?)(?:\?|$)", "recall"),
            (r"(?:remember|recall) (?:when|that) (.+?)(?:\?|$)", "recall"),
            (r"(?:the|my|our) (.+?) (?:project|plan|idea|thing)", "topic"),
            (r"last (?:time|week|month) (?:we|i) (.+?)(?:\?|$)", "temporal"),
        ]
        
        for pattern, _ in memory_reference_patterns:
            match = re.search(pattern, text_lower)
            if match:
                topic_keywords.append(match.group(1).strip())
        
        # Extract named entities (simple version)
        words = text.split()
        for word in words:
            if word[0].isupper() and len(word) > 2 and word.lower() not in [
                "the", "what", "when", "where", "how", "why", "can", "could",
                "would", "should", "did", "does", "barnabee", "hey", "hi"
            ]:
                topic_keywords.append(word)
        
        # Look for family member references
        family_patterns = [
            r"(?:thom|marci|penelope|xander|zachary|viola)",
            r"(?:dad|mom|kids?|children)",
        ]
        relevant_people = []
        for pattern in family_patterns:
            matches = re.findall(pattern, text_lower)
            relevant_people.extend(matches)
        
        # Determine time context
        time_context = None
        if "yesterday" in text_lower:
            time_context = "yesterday"
        elif "last week" in text_lower:
            time_context = "last_week"
        elif "this morning" in text_lower:
            time_context = "today_morning"
        elif "recently" in text_lower or "lately" in text_lower:
            time_context = "recent"
        
        # Build primary query
        primary_query = " ".join(topic_keywords) if topic_keywords else text[:100]
        
        # Build secondary queries (variations)
        secondary_queries = []
        if speaker_id and topic_keywords:
            secondary_queries.append(f"{speaker_id} {' '.join(topic_keywords)}")
        if relevant_people and topic_keywords:
            for person in relevant_people[:2]:
                secondary_queries.append(f"{person} {' '.join(topic_keywords)}")
        
        confidence = min(0.85, 0.4 + (len(topic_keywords) * 0.15))
        
        return MemoryQuerySet(
            primary_query=primary_query,
            secondary_queries=secondary_queries[:self.meta_config.max_secondary_queries],
            topic_tags=topic_keywords,
            relevant_people=list(set(relevant_people)),
            time_context=time_context,
            memory_types=self._infer_memory_types(text_lower),
            confidence=confidence,
        )
    
    async def _llm_query_generation(
        self,
        text: str,
        speaker_id: str,
        context: dict,
    ) -> MemoryQuerySet:
        """LLM-based query generation for complex requests."""
        from ..llm import LLMRouter
        
        prompt = self._get_memory_query_prompt(text, speaker_id, context)
        
        try:
            llm = LLMRouter(self.hass, self.config)
            response = await asyncio.wait_for(
                llm.async_complete(
                    prompt=prompt,
                    model=self.meta_config.meta_llm_model,
                    max_tokens=150,
                    temperature=0.3,  # Lower temperature for structured output
                ),
                timeout=self.meta_config.memory_query_timeout_ms / 1000,
            )
            
            # Parse JSON response
            import json
            data = json.loads(response.strip())
            
            return MemoryQuerySet(
                primary_query=data.get("primary", text[:50]),
                secondary_queries=data.get("secondary", [])[:self.meta_config.max_secondary_queries],
                topic_tags=data.get("tags", []),
                relevant_people=data.get("people", []),
                time_context=data.get("time_context"),
                memory_types=data.get("memory_types", ["experience"]),
                confidence=0.85,
            )
            
        except Exception as e:
            _LOGGER.warning(f"LLM query generation failed: {e}")
            # Fall back to basic query
            return MemoryQuerySet(
                primary_query=text[:100],
                confidence=0.3,
            )
    
    def _infer_memory_types(self, text_lower: str) -> list[str]:
        """Infer which memory types are relevant."""
        types = []
        
        if any(w in text_lower for w in ["usually", "always", "routine", "every"]):
            types.append("routine")
        if any(w in text_lower for w in ["prefer", "like", "favorite", "hate"]):
            types.append("preference")
        if any(w in text_lower for w in ["happened", "did", "was", "were", "said"]):
            types.append("event")
        if any(w in text_lower for w in ["feel", "think", "opinion", "relationship"]):
            types.append("relationship")
        
        return types if types else ["experience"]  # Default type
```

### Memory Query Examples

| User Input | Generated Queries |
|------------|-------------------|
| "What did I say about the garage project?" | **Primary:** `garage project`<br>**Secondary:** `thom garage project`, `home improvement plans`<br>**Tags:** `garage`, `project`<br>**Time:** `recent` |
| "Remember when we talked about Penelope's school?" | **Primary:** `penelope school`<br>**Secondary:** `kids education`, `penelope activities`<br>**People:** `penelope`<br>**Types:** `event`, `relationship` |
| "What's Marci's usual bedtime routine?" | **Primary:** `marci bedtime routine`<br>**People:** `marci`<br>**Types:** `routine` |

---

## Responsibility 4: Deferred Proactive Evaluation

**Critical Pattern:** Proactive suggestions are NOT delivered immediately. They are queued and only delivered when the interaction queue is nearly empty.

```python
    async def queue_proactive_suggestion(
        self,
        suggestion: ProactiveCandidate
    ) -> bool:
        """
        Queue a proactive suggestion - does NOT deliver immediately.
        Delivery is gated by should_proactively_speak().
        """
        async with self._proactive_lock:
            # Check queue size limit
            if len(self._proactive_queue) >= self.meta_config.proactive_queue_max_size:
                # Remove lowest priority or oldest
                self._proactive_queue.sort(key=lambda x: (x.priority, x.created_at))
                self._proactive_queue.pop(0)
            
            # Set expiration if not set
            if suggestion.expires_at is None:
                suggestion.expires_at = datetime.now() + timedelta(
                    seconds=self.meta_config.proactive_suggestion_ttl_seconds
                )
            
            self._proactive_queue.append(suggestion)
            self._proactive_queue.sort(key=lambda x: -x.priority)  # Highest priority first
            
            _LOGGER.debug(
                f"Queued proactive suggestion: {suggestion.suggestion_id} "
                f"(priority={suggestion.priority}, queue_size={len(self._proactive_queue)})"
            )
            return True
    
    async def should_proactively_speak(self) -> tuple[bool, Optional[ProactiveCandidate]]:
        """
        Determine if Barnabee should proactively speak now.
        
        Returns (should_speak, suggestion) where suggestion is the
        highest-priority queued item if should_speak is True.
        
        Gating conditions:
        1. No pending user interactions
        2. Sufficient time since last user interaction
        3. Sufficient time since last Barnabee speech
        4. No active conversation in progress
        5. At least one valid (non-expired) suggestion in queue
        """
        async with self._proactive_lock:
            state = self._interaction_state
            now = datetime.now()
            config = self.meta_config
            
            # ─────────────────────────────────────────────────────────────────
            # GATE 1: Check pending interactions
            # ─────────────────────────────────────────────────────────────────
            if state.pending_requests > config.proactive_max_pending_interactions:
                _LOGGER.debug(
                    f"Proactive blocked: {state.pending_requests} pending interactions "
                    f"(max={config.proactive_max_pending_interactions})"
                )
                return False, None
            
            # ─────────────────────────────────────────────────────────────────
            # GATE 2: Check active conversations
            # ─────────────────────────────────────────────────────────────────
            if state.active_conversations > 0:
                _LOGGER.debug(
                    f"Proactive blocked: {state.active_conversations} active conversations"
                )
                return False, None
            
            # ─────────────────────────────────────────────────────────────────
            # GATE 3: Check minimum silence since user interaction
            # ─────────────────────────────────────────────────────────────────
            if state.last_user_interaction:
                silence_duration = (now - state.last_user_interaction).total_seconds()
                if silence_duration < config.proactive_min_silence_seconds:
                    _LOGGER.debug(
                        f"Proactive blocked: only {silence_duration:.1f}s since user interaction "
                        f"(min={config.proactive_min_silence_seconds}s)"
                    )
                    return False, None
            
            # ─────────────────────────────────────────────────────────────────
            # GATE 4: Check cooldown since last Barnabee speech
            # ─────────────────────────────────────────────────────────────────
            if state.last_barnabee_speech:
                cooldown_remaining = (now - state.last_barnabee_speech).total_seconds()
                if cooldown_remaining < config.proactive_conversation_cooldown_seconds:
                    _LOGGER.debug(
                        f"Proactive blocked: only {cooldown_remaining:.1f}s since last speech "
                        f"(cooldown={config.proactive_conversation_cooldown_seconds}s)"
                    )
                    return False, None
            
            # ─────────────────────────────────────────────────────────────────
            # GATE 5: Find valid non-expired suggestion
            # ─────────────────────────────────────────────────────────────────
            # Clean expired suggestions
            self._proactive_queue = [
                s for s in self._proactive_queue
                if s.expires_at is None or s.expires_at > now
            ]
            
            if not self._proactive_queue:
                return False, None
            
            # Get highest priority suggestion
            suggestion = self._proactive_queue[0]
            
            _LOGGER.info(
                f"Proactive approved: delivering suggestion {suggestion.suggestion_id} "
                f"(priority={suggestion.priority})"
            )
            
            # Remove from queue
            self._proactive_queue.pop(0)
            
            return True, suggestion
    
    async def get_proactive_queue_status(self) -> dict:
        """Get current proactive queue status for monitoring."""
        async with self._proactive_lock:
            now = datetime.now()
            valid_count = sum(
                1 for s in self._proactive_queue
                if s.expires_at is None or s.expires_at > now
            )
            
            return {
                "queue_size": len(self._proactive_queue),
                "valid_suggestions": valid_count,
                "pending_interactions": self._interaction_state.pending_requests,
                "active_conversations": self._interaction_state.active_conversations,
                "last_user_interaction": (
                    self._interaction_state.last_user_interaction.isoformat()
                    if self._interaction_state.last_user_interaction else None
                ),
                "last_barnabee_speech": (
                    self._interaction_state.last_barnabee_speech.isoformat()
                    if self._interaction_state.last_barnabee_speech else None
                ),
            }
```

### Interaction State Management

```python
    async def _update_interaction_state(self, request: AgentRequest) -> None:
        """Update interaction state when processing a request."""
        async with self._state_lock:
            self._interaction_state.last_user_interaction = datetime.now()
            self._interaction_state.pending_requests += 1
    
    async def _handle_interaction_started(self, message: dict) -> None:
        """Handle interaction started event."""
        async with self._state_lock:
            self._interaction_state.active_conversations += 1
            if message.get("speaker"):
                self._interaction_state.current_speaker = message["speaker"]
    
    async def _handle_interaction_completed(self, message: dict) -> None:
        """Handle interaction completed event."""
        async with self._state_lock:
            self._interaction_state.pending_requests = max(
                0, self._interaction_state.pending_requests - 1
            )
            if message.get("barnabee_spoke"):
                self._interaction_state.last_barnabee_speech = datetime.now()
            if message.get("conversation_ended"):
                self._interaction_state.active_conversations = max(
                    0, self._interaction_state.active_conversations - 1
                )
                self._interaction_state.current_speaker = None
                self._interaction_state.conversation_depth = 0
    
    async def mark_barnabee_spoke(self) -> None:
        """Mark that Barnabee just spoke (for proactive gating)."""
        async with self._state_lock:
            self._interaction_state.last_barnabee_speech = datetime.now()
```

---

## Prompt Templates

### Intent Classification Prompt

```python
    def _get_classification_prompt(self, text: str, context: dict) -> str:
        """Get the intent classification prompt."""
        return f"""Classify the following user request into one of these categories:
- instant: Simple factual queries (time, date, greetings, math)
- action: Device control commands (lights, locks, thermostats, media)
- query: Information requests about home state or general knowledge
- conversation: Multi-turn dialogue, complex reasoning, creative requests
- memory: Requests to remember or recall personal information
- emergency: Safety-critical requests (fire, medical, security)

User request: "{text}"

Context: {context.get('history', [])[-3:] if context.get('history') else 'No previous context'}

Respond with only the category name and confidence (0.0-1.0), separated by comma.
Example: action, 0.85"""
```

### Memory Query Generation Prompt

```python
    def _get_memory_query_prompt(
        self,
        text: str,
        speaker_id: str,
        context: dict
    ) -> str:
        """Get the memory query generation prompt."""
        return f"""Generate semantic search queries to retrieve relevant memories for this request.
The user "{speaker_id}" said: "{text}"

Recent context: {context.get('history', [])[-2:] if context.get('history') else 'None'}

Output JSON with these fields:
- "primary": The main search query (string)
- "secondary": Alternative queries, max 3 (array of strings)
- "tags": Relevant topic keywords (array of strings)
- "people": Family members mentioned or implied (array of strings)
- "time_context": Time reference if any - "recent", "yesterday", "last_week", etc. (string or null)
- "memory_types": Relevant types - "routine", "preference", "event", "relationship" (array of strings)

Example for "What did I say about the garage project?":
{{"primary": "garage project", "secondary": ["home improvement plans", "thom projects"], "tags": ["garage", "project", "renovation"], "people": ["thom"], "time_context": "recent", "memory_types": ["event", "preference"]}}

Respond with only valid JSON, no explanation."""
```

### Context Evaluation Prompt (Jinja2 Template)

```jinja
{# prompts/meta/context_evaluation.prompt #}
Analyze the emotional context of this user request.

User: {{ speaker_name }} ({{ speaker_role }})
Request: "{{ text }}"

{% if conversation_history %}
Recent conversation:
{% for turn in conversation_history[-3:] %}
{{ turn.speaker }}: {{ turn.text }}
{% endfor %}
{% endif %}

Evaluate and respond with JSON:
{
  "emotional_tone": "neutral|positive|negative|stressed|confused|urgent",
  "urgency_level": "low|medium|high|emergency",
  "empathy_needed": true|false,
  "detected_emotions": ["list", "of", "emotions"],
  "suggested_response_tone": "friendly|warm|empathetic|calm_urgent|professional"
}

Consider:
- Word choice and intensity
- Punctuation (!!! or ???)
- Time pressure indicators
- Signs of frustration or stress
- Whether the request needs emotional acknowledgment

Respond with only valid JSON.
```

---

## Integration Patterns

### Proactive Orchestrator

```python
class ProactiveOrchestrator:
    """Manages the proactive suggestion delivery loop."""
    
    def __init__(
        self,
        meta_agent: MetaAgent,
        proactive_agent: ProactiveAgent,
        voice_pipeline: VoicePipeline,
    ):
        self.meta_agent = meta_agent
        self.proactive_agent = proactive_agent
        self.voice = voice_pipeline
        self._running = False
    
    async def start_proactive_loop(self) -> None:
        """Start the background proactive evaluation loop."""
        self._running = True
        
        while self._running:
            try:
                # Check if we should proactively speak
                should_speak, suggestion = await self.meta_agent.should_proactively_speak()
                
                if should_speak and suggestion:
                    # Deliver the proactive suggestion
                    await self._deliver_proactive_suggestion(suggestion)
                
                # Check every second
                await asyncio.sleep(1.0)
                
            except Exception as e:
                _LOGGER.error(f"Proactive loop error: {e}")
                await asyncio.sleep(5.0)
    
    async def _deliver_proactive_suggestion(
        self,
        suggestion: ProactiveCandidate
    ) -> None:
        """Deliver a proactive suggestion to the user."""
        _LOGGER.info(f"Delivering proactive suggestion: {suggestion.content}")
        
        # Generate speech
        audio = await self.voice.synthesize(suggestion.content)
        
        # Play in target room or default
        target = suggestion.target_room or "living_room"
        await self.voice.play_audio(audio, location=target)
        
        # Mark that Barnabee spoke (for cooldown)
        await self.meta_agent.mark_barnabee_spoke()
        
        # Log for observability
        await self.proactive_agent.log_delivery(suggestion)
    
    async def stop(self) -> None:
        """Stop the proactive loop."""
        self._running = False
```

### Helper Methods

```python
    def _determine_target_agent(self, intent: IntentCategory) -> str:
        """Map intent to target agent."""
        mapping = {
            IntentCategory.INSTANT: "instant_agent",
            IntentCategory.ACTION: "action_agent",
            IntentCategory.QUERY: "interaction_agent",
            IntentCategory.CONVERSATION: "interaction_agent",
            IntentCategory.MEMORY: "memory_agent",
            IntentCategory.EMERGENCY: "action_agent",  # Emergency actions
            IntentCategory.PROACTIVE: "proactive_agent",
            IntentCategory.GESTURE: "instant_agent",
            IntentCategory.UNKNOWN: "interaction_agent",
        }
        return mapping.get(intent, "interaction_agent")
    
    def _calculate_priority(
        self,
        classification: ClassificationResult,
        context_eval: Optional[ContextEvaluation],
    ) -> int:
        """Calculate request priority (1-10, higher = more urgent)."""
        base_priority = 5
        
        # Intent-based adjustments
        intent_priority = {
            IntentCategory.EMERGENCY: 10,
            IntentCategory.ACTION: 7,
            IntentCategory.INSTANT: 6,
            IntentCategory.GESTURE: 6,
            IntentCategory.QUERY: 5,
            IntentCategory.CONVERSATION: 4,
            IntentCategory.MEMORY: 4,
            IntentCategory.PROACTIVE: 3,
        }
        base_priority = intent_priority.get(classification.intent, 5)
        
        # Urgency adjustments from context
        if context_eval:
            urgency_boost = {
                UrgencyLevel.EMERGENCY: 3,
                UrgencyLevel.HIGH: 2,
                UrgencyLevel.MEDIUM: 1,
                UrgencyLevel.LOW: 0,
            }
            base_priority += urgency_boost.get(context_eval.urgency_level, 0)
        
        return min(10, max(1, base_priority))
```

---

## Summary of Changes from Original

| Aspect | Before | After |
|--------|--------|-------|
| **Responsibilities** | 1 (routing only) | 4 (routing + context + memory queries + proactive gating) |
| **Data Structures** | `ClassificationResult` only | + `ContextEvaluation`, `MemoryQuerySet`, `ProactiveCandidate`, `InteractionState` |
| **Latency Target** | 20ms | 50ms (accounts for additional evaluation) |
| **Proactive Behavior** | Immediate delivery | Deferred with queue and gating conditions |
| **Memory Integration** | None | Generates queries for Memory Agent |
| **Emotional Awareness** | None | Detects tone, urgency, empathy needs |
| **Emergency Handling** | Via action patterns | Dedicated emergency patterns with highest priority |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial Meta Agent specification with four responsibilities |

---

*This document complements BarnabeeNet_Technical_Architecture.md with detailed Meta Agent specifications. For the full system architecture, see the Technical Architecture document.*
