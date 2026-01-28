# Area 08: Self-Improvement Pipeline

**Version:** 2.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01, 03, 05 (Data Layer, Intent Classification, Memory)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

The Self-Improvement Pipeline enables Barnabee to learn from three sources:
1. **Automatic signals** - Learn passively from production traffic (LLM fallbacks, corrections, failures)
2. **User suggestions** - Learn from explicit teaching via dashboard or voice
3. **Feedback loop** - Learn from in-conversation corrections

All learning enforces strict safety boundaries to prevent the "Timer fix → Dashboard crash" failure mode from V1.

### 1.2 V1 Failure Analysis

**What happened:** V1's self-improvement modified shared utility functions. A "fix" to timer handling code cascaded to dashboard rendering, causing production outage.

**Root causes:**
1. No isolation between improvement targets
2. No staging/shadow deployment
3. No rollback mechanism
4. No blast radius containment
5. Modifications touched code, not just data

### 1.3 V2 Design Principles

1. **Data, not code:** Self-improvement modifies classifier weights, exemplars, aliases—never application code.
2. **Three-tier approval:** Tier 1 auto-applies; Tier 2 requires human approval; Tier 3 is forbidden.
3. **Shadow testing:** All changes tested against golden dataset before deployment.
4. **Automatic rollback:** Metrics degradation triggers instant rollback.
5. **Audit trail:** Every change is logged with provenance.

### 1.4 What Can Be Improved

| Target | Tier | Auto-Apply | Example |
|--------|------|------------|---------|
| Entity aliases | 1 | ✓ | "liv room" → "living room" |
| Classifier exemplars | 1 | ✓ | New phrasing for existing intent |
| Keyword synonyms | 1 | ✓ | "switch on" = "turn on" |
| Intent patterns | 2 | ✗ | New intent sub-category |
| Handler routing | 2 | ✗ | Intent → handler mapping |
| Response templates | 2 | ✗ | New template variants |
| Core pipeline code | 3 | ✗ | FORBIDDEN |
| Database schema | 3 | ✗ | FORBIDDEN |
| API contracts | 3 | ✗ | FORBIDDEN |
| Security settings | 3 | ✗ | FORBIDDEN |

---

## 2. Architecture

### 2.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SELF-IMPROVEMENT PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA COLLECTION                                                             │
│  ═══════════════                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    IMPROVEMENT SIGNALS                               │   │
│  │                                                                      │   │
│  │  • LLM fallbacks (classifier couldn't handle)                       │   │
│  │  • User corrections ("no, I meant...")                              │   │
│  │  • Entity resolution failures                                       │   │
│  │  • Low-confidence classifications                                   │   │
│  │  • Explicit feedback ("that was wrong")                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  ANALYSIS                                                                    │
│  ════════                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    IMPROVEMENT ANALYZER                              │   │
│  │                                                                      │   │
│  │  1. Cluster similar signals                                         │   │
│  │  2. Identify recurring patterns (threshold: 3+ occurrences)         │   │
│  │  3. Classify improvement type                                       │   │
│  │  4. Assign tier (1, 2, or 3)                                        │   │
│  │  5. Generate proposed change                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  VALIDATION                                                                  │
│  ══════════                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SHADOW TESTING                                    │   │
│  │                                                                      │   │
│  │  1. Apply change to shadow copy                                     │   │
│  │  2. Run golden dataset (500+ labeled examples)                      │   │
│  │  3. Compare metrics: accuracy, latency, regression                  │   │
│  │  4. Pass/fail decision                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│              ┌──────┴──────┐                                                │
│              │             │                                                │
│           PASS          FAIL                                                │
│              │             │                                                │
│              ▼             ▼                                                │
│  ┌───────────────┐  ┌───────────────┐                                      │
│  │ TIER CHECK    │  │   DISCARD     │                                      │
│  └───────┬───────┘  │   + LOG       │                                      │
│          │          └───────────────┘                                      │
│    ┌─────┴─────┐                                                           │
│    │           │                                                           │
│  TIER 1     TIER 2                                                         │
│    │           │                                                           │
│    ▼           ▼                                                           │
│  ┌─────────┐  ┌─────────────────────────────────────────────┐             │
│  │ AUTO    │  │         PENDING_IMPROVEMENTS TABLE          │             │
│  │ APPLY   │  │                                             │             │
│  └────┬────┘  │  Awaits human approval via dashboard        │             │
│       │       └─────────────────────────────────────────────┘             │
│       │                                                                    │
│       ▼                                                                    │
│  DEPLOYMENT                                                                │
│  ══════════                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    ATOMIC DEPLOYMENT                                 │  │
│  │                                                                      │  │
│  │  1. Create backup of current state                                  │  │
│  │  2. Apply change atomically                                         │  │
│  │  3. Record change in audit log                                      │  │
│  │  4. Start monitoring window (24h)                                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                     │                                                       │
│                     ▼                                                       │
│  MONITORING                                                                 │
│  ══════════                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    POST-DEPLOYMENT MONITORING                        │  │
│  │                                                                      │  │
│  │  Monitor for 24 hours:                                              │  │
│  │  • Classification accuracy (must stay >95%)                         │  │
│  │  • Latency P95 (must stay <target)                                  │  │
│  │  • Error rate (must stay <1%)                                       │  │
│  │  • User correction rate (must not increase)                         │  │
│  │                                                                      │  │
│  │  If degradation detected → AUTOMATIC ROLLBACK                       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Three Input Sources

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SELF-IMPROVEMENT INPUT SOURCES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. AUTOMATIC SIGNALS (passive learning)                                     │
│  ═══════════════════════════════════════                                    │
│                                                                              │
│  Collected automatically from production traffic:                            │
│  • LLM fallbacks (classifier couldn't handle, LLM resolved it)              │
│  • Entity resolution failures (couldn't find device, LLM guessed)           │
│  • Low confidence classifications                                           │
│  • User corrections detected in conversation ("no, I meant...")             │
│                                                                              │
│  Flow: Signal → Cluster → Analyze → Propose → Shadow Test → Deploy          │
│                                                                              │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  2. USER SUGGESTIONS (active learning via Dashboard)                         │
│  ══════════════════════════════════════════════════                         │
│                                                                              │
│  Submitted via Dashboard → Improve → Add Suggestion:                         │
│  • Entity aliases: "When I say 'liv room lamp', I mean light.living_room"   │
│  • Training examples: "Add 'lights please' as example for light_control"    │
│  • Synonyms: "switch on" should equal "turn on"                             │
│                                                                              │
│  Flow: Suggestion → Shadow Test → (Approve if Tier 2) → Deploy              │
│  Note: User suggestions skip clustering, go straight to shadow test         │
│                                                                              │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  3. VOICE LEARNING COMMANDS (conversational learning)                        │
│  ═════════════════════════════════════════════════════                      │
│                                                                              │
│  Spoken naturally during conversation:                                       │
│  • "Barnabee, remember that 'liv room' means living room"                   │
│  • "When I say bedroom lamp, I mean the nightstand light"                   │
│  • "No, I meant the other light" (correction + learning)                    │
│  • "That was wrong" (negative feedback for investigation)                   │
│                                                                              │
│  Flow: Voice Command → Parse → Create Suggestion → Shadow Test → Deploy     │
│                                                                              │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  All three sources feed into the same pipeline:                              │
│                                                                              │
│       ┌──────────────┐                                                      │
│       │  Automatic   │───┐                                                  │
│       │   Signals    │   │                                                  │
│       └──────────────┘   │    ┌──────────────┐    ┌──────────────┐         │
│                          ├───▶│ Shadow Test  │───▶│   Deploy     │         │
│       ┌──────────────┐   │    └──────────────┘    └──────────────┘         │
│       │    User      │───┤                                                  │
│       │ Suggestions  │   │                                                  │
│       └──────────────┘   │                                                  │
│                          │                                                  │
│       ┌──────────────┐   │                                                  │
│       │    Voice     │───┘                                                  │
│       │  Commands    │                                                      │
│       └──────────────┘                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Data Model

```sql
-- Improvement signals from production
CREATE TABLE improvement_signals (
    id TEXT PRIMARY KEY,
    signal_type TEXT NOT NULL,  -- 'llm_fallback', 'correction', 'entity_fail', 'low_confidence', 'feedback'
    utterance TEXT NOT NULL,
    context TEXT,  -- JSON: intent, entities, confidence, etc.
    expected_outcome TEXT,  -- What user wanted
    actual_outcome TEXT,    -- What system did
    speaker_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    improvement_id TEXT  -- Links to resulting improvement if any
);

-- Proposed improvements (pending and applied)
CREATE TABLE improvements (
    id TEXT PRIMARY KEY,
    improvement_type TEXT NOT NULL,  -- 'alias', 'exemplar', 'synonym', 'pattern', 'template'
    tier INTEGER NOT NULL,  -- 1, 2, or 3
    target TEXT NOT NULL,  -- What's being modified
    current_value TEXT,    -- Current state (for rollback)
    proposed_value TEXT NOT NULL,  -- Proposed change
    rationale TEXT,        -- Why this change
    signal_ids TEXT,       -- JSON array of contributing signal IDs
    
    -- Source tracking (NEW: supports user suggestions and voice learning)
    source TEXT DEFAULT 'automatic',  -- 'automatic', 'user_suggestion', 'voice_command'
    submitted_by TEXT,     -- User who submitted (for user_suggestion/voice_command)
    
    -- Validation results
    shadow_test_passed BOOLEAN,
    shadow_test_results TEXT,  -- JSON: metrics before/after
    
    -- Status
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'applied', 'rolled_back', 'rejected'
    approved_by TEXT,
    approved_at DATETIME,
    applied_at DATETIME,
    rolled_back_at DATETIME,
    
    -- Monitoring
    monitoring_start DATETIME,
    monitoring_end DATETIME,
    monitoring_results TEXT,  -- JSON: metrics during window
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Audit log for all changes
CREATE TABLE improvement_audit (
    id TEXT PRIMARY KEY,
    improvement_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'created', 'tested', 'approved', 'applied', 'rolled_back'
    actor TEXT,  -- 'system' or user ID
    details TEXT,  -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Signal Collection

### 3.1 Signal Types

```python
class SignalType(Enum):
    LLM_FALLBACK = "llm_fallback"      # Classifier couldn't handle, used LLM
    CORRECTION = "correction"           # User corrected system behavior
    ENTITY_FAIL = "entity_fail"         # Entity resolution failed
    LOW_CONFIDENCE = "low_confidence"   # Classification confidence < threshold
    EXPLICIT_FEEDBACK = "feedback"      # User said "that was wrong"


@dataclass
class ImprovementSignal:
    id: str
    signal_type: SignalType
    utterance: str
    context: dict  # Full classification context
    expected_outcome: Optional[str]  # What user wanted
    actual_outcome: Optional[str]    # What happened
    speaker_id: Optional[str]
    created_at: datetime
```

### 3.2 Signal Collector

```python
class SignalCollector:
    """Collect improvement signals from production traffic."""
    
    def __init__(self, db: Database):
        self.db = db
        self.CORRECTION_PATTERNS = [
            r"no,?\s*i\s*(?:meant|said|want)",
            r"that'?s?\s*(?:not|wrong)",
            r"i\s*didn'?t\s*(?:mean|say|want)",
            r"not\s+(?:that|what\s+i)",
        ]
    
    async def record_llm_fallback(
        self,
        utterance: str,
        classification_result: ClassificationResult,
    ):
        """Record when classifier fell back to LLM."""
        if classification_result.stage != "llm":
            return  # Not a fallback
        
        signal = ImprovementSignal(
            id=generate_uuid(),
            signal_type=SignalType.LLM_FALLBACK,
            utterance=utterance,
            context={
                "intent": classification_result.intent,
                "confidence": classification_result.confidence,
                "entities": classification_result.entities,
            },
            expected_outcome=None,
            actual_outcome=classification_result.intent,
            speaker_id=None,
            created_at=datetime.utcnow(),
        )
        
        await self._save_signal(signal)
    
    async def record_correction(
        self,
        correction_utterance: str,
        previous_utterance: str,
        previous_result: ClassificationResult,
    ):
        """Record user correction."""
        # Check if this looks like a correction
        if not self._is_correction(correction_utterance):
            return
        
        signal = ImprovementSignal(
            id=generate_uuid(),
            signal_type=SignalType.CORRECTION,
            utterance=previous_utterance,
            context={
                "correction_text": correction_utterance,
                "original_intent": previous_result.intent,
                "original_confidence": previous_result.confidence,
            },
            expected_outcome=None,  # Will be inferred
            actual_outcome=previous_result.intent,
            speaker_id=None,
            created_at=datetime.utcnow(),
        )
        
        await self._save_signal(signal)
    
    async def record_entity_failure(
        self,
        utterance: str,
        entity_text: str,
        resolution_attempted: str,
    ):
        """Record entity resolution failure."""
        signal = ImprovementSignal(
            id=generate_uuid(),
            signal_type=SignalType.ENTITY_FAIL,
            utterance=utterance,
            context={
                "entity_text": entity_text,
                "resolution_attempted": resolution_attempted,
            },
            expected_outcome=None,
            actual_outcome="unresolved",
            speaker_id=None,
            created_at=datetime.utcnow(),
        )
        
        await self._save_signal(signal)
    
    async def record_low_confidence(
        self,
        utterance: str,
        result: ClassificationResult,
        threshold: float = 0.70,
    ):
        """Record low-confidence classification."""
        if result.confidence >= threshold:
            return
        
        signal = ImprovementSignal(
            id=generate_uuid(),
            signal_type=SignalType.LOW_CONFIDENCE,
            utterance=utterance,
            context={
                "intent": result.intent,
                "confidence": result.confidence,
                "stage": result.stage,
            },
            expected_outcome=None,
            actual_outcome=result.intent,
            speaker_id=None,
            created_at=datetime.utcnow(),
        )
        
        await self._save_signal(signal)
    
    def _is_correction(self, text: str) -> bool:
        """Check if utterance looks like a correction."""
        text_lower = text.lower()
        return any(
            re.search(pattern, text_lower) 
            for pattern in self.CORRECTION_PATTERNS
        )
    
    async def _save_signal(self, signal: ImprovementSignal):
        """Persist signal to database."""
        await self.db.execute(
            """
            INSERT INTO improvement_signals 
            (id, signal_type, utterance, context, expected_outcome, 
             actual_outcome, speaker_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                signal.id,
                signal.signal_type.value,
                signal.utterance,
                json.dumps(signal.context),
                signal.expected_outcome,
                signal.actual_outcome,
                signal.speaker_id,
                signal.created_at.isoformat(),
            ]
        )
```

### 3.3 User Suggestions (Dashboard Input)

Users can submit improvement suggestions directly via the Dashboard. These bypass the signal clustering step and go straight to shadow testing.

```python
class UserSuggestionService:
    """Handle user-submitted improvement suggestions from Dashboard."""
    
    def __init__(self, db: Database, shadow_tester: 'ShadowTestRunner'):
        self.db = db
        self.shadow_tester = shadow_tester
    
    async def submit_suggestion(
        self,
        suggestion_type: str,  # 'alias', 'training_example', 'synonym'
        source_text: str,      # "When I say this..."
        target: str,           # "I mean this..."
        submitted_by: str,
        note: Optional[str] = None,
    ) -> 'Improvement':
        """
        Submit a user suggestion for improvement.
        
        Examples:
            - alias: source="liv room lamp", target="light.living_room_lamp"
            - training_example: source="lights please", target="light_control"
            - synonym: source="switch on", target="turn on"
        """
        
        # Determine tier based on type
        tier = 1 if suggestion_type in ['alias', 'synonym', 'training_example'] else 2
        
        # Create improvement record
        improvement = Improvement(
            id=generate_uuid(),
            improvement_type=suggestion_type,
            tier=tier,
            target=self._format_target(suggestion_type, target),
            current_value=None,
            proposed_value=json.dumps({
                "source_text": source_text,
                "target": target,
            }),
            rationale=f"User suggestion from {submitted_by}" + (f": {note}" if note else ""),
            signal_ids=[],  # No signals - direct user input
            source="user_suggestion",
            submitted_by=submitted_by,
        )
        
        # Run shadow test immediately
        passed, results = await self.shadow_tester.test_improvement(improvement)
        improvement.shadow_test_passed = passed
        improvement.shadow_test_results = results
        
        # Save to pending improvements
        await self._save_improvement(improvement)
        
        # Audit log
        await self._audit_log(improvement, "user_suggestion_created", submitted_by)
        
        return improvement
    
    def _format_target(self, suggestion_type: str, target: str) -> str:
        """Format target based on suggestion type."""
        if suggestion_type == 'alias':
            return f"entity:{target}"
        elif suggestion_type == 'training_example':
            return f"intent:{target}"
        elif suggestion_type == 'synonym':
            return f"synonym:{target}"
        return target
    
    async def _save_improvement(self, improvement: 'Improvement'):
        """Save improvement to database."""
        await self.db.execute(
            """
            INSERT INTO improvements 
            (id, improvement_type, tier, target, current_value, proposed_value,
             rationale, signal_ids, source, submitted_by, shadow_test_passed,
             shadow_test_results, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            [
                improvement.id,
                improvement.improvement_type,
                improvement.tier,
                improvement.target,
                improvement.current_value,
                improvement.proposed_value,
                improvement.rationale,
                json.dumps(improvement.signal_ids),
                improvement.source,
                improvement.submitted_by,
                improvement.shadow_test_passed,
                json.dumps(improvement.shadow_test_results),
                datetime.utcnow().isoformat(),
            ]
        )


# Dashboard API endpoint
@router.post("/api/dashboard/improvements/suggest")
async def submit_improvement_suggestion(
    suggestion: UserSuggestionRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Submit a user improvement suggestion.
    
    Request body:
    {
        "type": "alias",
        "source_text": "liv room lamp",
        "target": "light.living_room_lamp",
        "note": "optional context"
    }
    """
    improvement = await suggestion_service.submit_suggestion(
        suggestion_type=suggestion.type,
        source_text=suggestion.source_text,
        target=suggestion.target,
        submitted_by=user["username"],
        note=suggestion.note,
    )
    
    return {
        "id": improvement.id,
        "status": "pending",
        "shadow_test_passed": improvement.shadow_test_passed,
        "message": "Suggestion submitted and tested. " + 
                   ("Ready for approval." if improvement.shadow_test_passed else "Shadow test failed."),
    }
```

### 3.4 Voice Learning Commands

Users can teach Barnabee through natural conversation. These voice commands are recognized, parsed, and converted into improvement suggestions.

```python
class VoiceLearningHandler:
    """
    Handle voice-based learning commands.
    
    Recognized patterns:
    - "Barnabee, remember that [X] means [Y]"
    - "When I say [X], I mean [Y]"
    - "No, I meant [Y]" (correction + learning)
    - "That was wrong" / "That's not right" (negative feedback)
    """
    
    LEARNING_PATTERNS = {
        # Alias teaching
        r"(?:barnabee,?\s*)?remember\s+that\s+['\"]?(.+?)['\"]?\s+(?:means|is)\s+['\"]?(.+?)['\"]?$": "teach_alias",
        r"when\s+i\s+say\s+['\"]?(.+?)['\"]?,?\s*i\s+mean\s+['\"]?(.+?)['\"]?$": "teach_alias",
        r"['\"]?(.+?)['\"]?\s+(?:should\s+)?mean[s]?\s+['\"]?(.+?)['\"]?$": "teach_alias",
        
        # Corrections (with implicit learning)
        r"no,?\s*(?:i\s+)?meant?\s+(?:the\s+)?(.+)$": "correction",
        r"not\s+that\s+(?:one)?,?\s*(?:the\s+)?(.+)$": "correction",
        r"wrong\s+(?:one|light|device),?\s*(?:i\s+(?:want|meant)\s+)?(?:the\s+)?(.+)?$": "correction",
        
        # Negative feedback (for investigation)
        r"that\s*(?:was|is)?\s*(?:wrong|incorrect|not\s+(?:right|correct|what\s+i\s+(?:wanted|meant)))": "negative_feedback",
        r"(?:that's|thats)\s+not\s+(?:right|correct|what\s+i\s+(?:wanted|meant))": "negative_feedback",
        
        # Positive feedback (for reinforcement)
        r"(?:that's|thats|that\s+(?:was|is))\s+(?:right|correct|perfect|exactly|good)": "positive_feedback",
        r"(?:yes|yeah|yep),?\s*(?:that's|thats)?\s*(?:it|right|correct)?$": "positive_feedback",
    }
    
    def __init__(
        self,
        suggestion_service: UserSuggestionService,
        signal_collector: SignalCollector,
        ha_client: 'HAClient',
        executor: 'CommandExecutor',
    ):
        self.suggestion_service = suggestion_service
        self.signal_collector = signal_collector
        self.ha_client = ha_client
        self.executor = executor
    
    async def handle_utterance(
        self,
        utterance: str,
        context: 'ConversationContext',
    ) -> Optional['VoiceLearningResult']:
        """
        Check if utterance is a learning command and handle it.
        
        Returns VoiceLearningResult if handled, None if not a learning command.
        """
        
        utterance_lower = utterance.lower().strip()
        
        for pattern, learning_type in self.LEARNING_PATTERNS.items():
            match = re.search(pattern, utterance_lower, re.IGNORECASE)
            if match:
                return await self._handle_learning(
                    learning_type=learning_type,
                    match=match,
                    original_utterance=utterance,
                    context=context,
                )
        
        return None  # Not a learning command
    
    async def _handle_learning(
        self,
        learning_type: str,
        match: re.Match,
        original_utterance: str,
        context: 'ConversationContext',
    ) -> 'VoiceLearningResult':
        """Handle a detected learning command."""
        
        if learning_type == "teach_alias":
            return await self._handle_teach_alias(match, context)
        
        elif learning_type == "correction":
            return await self._handle_correction(match, context)
        
        elif learning_type == "negative_feedback":
            return await self._handle_negative_feedback(context)
        
        elif learning_type == "positive_feedback":
            return await self._handle_positive_feedback(context)
        
        return VoiceLearningResult(
            handled=False,
            response="I didn't understand that learning command.",
        )
    
    async def _handle_teach_alias(
        self,
        match: re.Match,
        context: 'ConversationContext',
    ) -> 'VoiceLearningResult':
        """
        Handle: "Remember that 'liv room' means living room lamp"
        """
        source_text = match.group(1).strip()
        target_text = match.group(2).strip()
        
        # Try to resolve target to an entity
        resolved_entity = await self.ha_client.resolve_entity(target_text)
        
        if resolved_entity:
            # Create improvement suggestion
            improvement = await self.suggestion_service.submit_suggestion(
                suggestion_type="alias",
                source_text=source_text,
                target=resolved_entity.entity_id,
                submitted_by=context.speaker_id or "voice",
                note=f"Voice command: '{context.original_utterance}'",
            )
            
            if improvement.shadow_test_passed:
                return VoiceLearningResult(
                    handled=True,
                    response=f"Got it! I'll remember that '{source_text}' means {resolved_entity.friendly_name}.",
                    improvement_id=improvement.id,
                )
            else:
                return VoiceLearningResult(
                    handled=True,
                    response=f"I understood, but that change didn't pass my tests. I've logged it for review.",
                    improvement_id=improvement.id,
                )
        else:
            return VoiceLearningResult(
                handled=True,
                response=f"I couldn't find a device called '{target_text}'. Can you be more specific?",
            )
    
    async def _handle_correction(
        self,
        match: re.Match,
        context: 'ConversationContext',
    ) -> 'VoiceLearningResult':
        """
        Handle: "No, I meant the bedroom light"
        
        This both executes the correction AND learns from it.
        """
        correct_target = match.group(1).strip() if match.lastindex else None
        
        if not context.previous_command:
            return VoiceLearningResult(
                handled=True,
                response="I'm not sure what you're correcting. What would you like me to do?",
            )
        
        # Try to resolve the correction target
        resolved_entity = await self.ha_client.resolve_entity(correct_target) if correct_target else None
        
        if resolved_entity:
            # Execute the corrected command
            await self.executor.execute_on_entity(
                entity_id=resolved_entity.entity_id,
                action=context.previous_command.action,
            )
            
            # Record correction for learning
            await self.signal_collector.record_correction(
                correction_utterance=context.original_utterance,
                previous_utterance=context.previous_command.utterance,
                previous_result=context.previous_command.classification,
                correct_entity=resolved_entity.entity_id,
            )
            
            # If we can infer an alias, suggest it
            if context.previous_command.unresolved_entity:
                await self.suggestion_service.submit_suggestion(
                    suggestion_type="alias",
                    source_text=context.previous_command.unresolved_entity,
                    target=resolved_entity.entity_id,
                    submitted_by=context.speaker_id or "voice",
                    note=f"Learned from correction: '{context.original_utterance}'",
                )
            
            return VoiceLearningResult(
                handled=True,
                response=f"Sorry about that. I've turned on the {resolved_entity.friendly_name} and I'll remember for next time.",
                executed_entity=resolved_entity.entity_id,
            )
        else:
            return VoiceLearningResult(
                handled=True,
                response="I'm not sure which device you mean. Can you be more specific?",
            )
    
    async def _handle_negative_feedback(
        self,
        context: 'ConversationContext',
    ) -> 'VoiceLearningResult':
        """
        Handle: "That was wrong"
        
        Records negative feedback for investigation.
        """
        if context.previous_command:
            await self.signal_collector.record_explicit_feedback(
                feedback_type="negative",
                previous_utterance=context.previous_command.utterance,
                previous_result=context.previous_command.classification,
                speaker_id=context.speaker_id,
            )
            
            return VoiceLearningResult(
                handled=True,
                response="Sorry about that. I've logged this for review. What did you want me to do?",
            )
        else:
            return VoiceLearningResult(
                handled=True,
                response="What was wrong? Let me know what you wanted.",
            )
    
    async def _handle_positive_feedback(
        self,
        context: 'ConversationContext',
    ) -> 'VoiceLearningResult':
        """
        Handle: "That's right" / "Perfect"
        
        Records positive feedback for reinforcement.
        """
        if context.previous_command:
            await self.signal_collector.record_explicit_feedback(
                feedback_type="positive",
                previous_utterance=context.previous_command.utterance,
                previous_result=context.previous_command.classification,
                speaker_id=context.speaker_id,
            )
        
        return VoiceLearningResult(
            handled=True,
            response="Great!",  # Keep it short for positive feedback
        )


@dataclass
class VoiceLearningResult:
    """Result of processing a voice learning command."""
    handled: bool
    response: str
    improvement_id: Optional[str] = None
    executed_entity: Optional[str] = None
```

---

## 4. Improvement Analysis

### 4.1 Analyzer

```python
class ImprovementAnalyzer:
    """Analyze signals and generate improvement proposals."""
    
    OCCURRENCE_THRESHOLD = 3  # Need 3+ similar signals to propose change
    
    def __init__(
        self,
        db: Database,
        llm_client: LLMClient,
        embedding_service: EmbeddingService,
    ):
        self.db = db
        self.llm = llm_client
        self.embedding = embedding_service
    
    async def analyze_pending_signals(self) -> List['Improvement']:
        """Analyze unprocessed signals and generate improvements."""
        
        # Get unprocessed signals
        signals = await self._get_unprocessed_signals()
        
        if len(signals) < self.OCCURRENCE_THRESHOLD:
            return []
        
        # Cluster similar signals
        clusters = await self._cluster_signals(signals)
        
        improvements = []
        
        for cluster in clusters:
            if len(cluster) < self.OCCURRENCE_THRESHOLD:
                continue
            
            # Analyze cluster
            improvement = await self._analyze_cluster(cluster)
            
            if improvement:
                improvements.append(improvement)
                
                # Mark signals as processed
                await self._mark_processed(cluster, improvement.id)
        
        return improvements
    
    async def _cluster_signals(
        self,
        signals: List[ImprovementSignal],
    ) -> List[List[ImprovementSignal]]:
        """Cluster signals by similarity."""
        
        # Generate embeddings
        embeddings = await self.embedding.embed_batch([s.utterance for s in signals])
        
        # Simple clustering: group by high similarity
        clusters = []
        used = set()
        
        for i, signal in enumerate(signals):
            if i in used:
                continue
            
            cluster = [signal]
            used.add(i)
            
            for j, other in enumerate(signals):
                if j in used:
                    continue
                
                similarity = self._cosine_similarity(embeddings[i], embeddings[j])
                if similarity > 0.85:  # High similarity threshold
                    cluster.append(other)
                    used.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _analyze_cluster(
        self,
        cluster: List[ImprovementSignal],
    ) -> Optional['Improvement']:
        """Analyze a cluster and propose improvement."""
        
        # Determine signal type (use most common)
        signal_types = [s.signal_type for s in cluster]
        primary_type = max(set(signal_types), key=signal_types.count)
        
        # Route to appropriate analyzer
        if primary_type == SignalType.LLM_FALLBACK:
            return await self._analyze_llm_fallback_cluster(cluster)
        
        elif primary_type == SignalType.ENTITY_FAIL:
            return await self._analyze_entity_fail_cluster(cluster)
        
        elif primary_type == SignalType.CORRECTION:
            return await self._analyze_correction_cluster(cluster)
        
        return None
    
    async def _analyze_llm_fallback_cluster(
        self,
        cluster: List[ImprovementSignal],
    ) -> Optional['Improvement']:
        """Analyze LLM fallback cluster → propose new exemplars."""
        
        # Extract utterances and intents
        utterances = [s.utterance for s in cluster]
        intents = [s.context.get("intent") for s in cluster]
        
        # Check if all same intent
        if len(set(intents)) == 1:
            intent = intents[0]
            
            # Propose adding exemplars
            return Improvement(
                id=generate_uuid(),
                improvement_type="exemplar",
                tier=1,  # Exemplar additions are low risk
                target=f"intent:{intent}",
                current_value=None,
                proposed_value=json.dumps(utterances),
                rationale=f"Adding {len(utterances)} new exemplars for intent '{intent}' based on {len(cluster)} LLM fallbacks",
                signal_ids=[s.id for s in cluster],
            )
        
        return None
    
    async def _analyze_entity_fail_cluster(
        self,
        cluster: List[ImprovementSignal],
    ) -> Optional['Improvement']:
        """Analyze entity failure cluster → propose new aliases."""
        
        # Extract entity texts
        entity_texts = [s.context.get("entity_text") for s in cluster]
        
        # Find most common failed entity text
        common_text = max(set(entity_texts), key=entity_texts.count)
        
        # Use LLM to guess what entity they meant
        prompt = f"""These phrases failed to resolve to a smart home device:
{json.dumps(entity_texts)}

Based on the pattern, what device are users trying to reference?
Respond with just the likely device name (e.g., "living room lights")."""

        likely_device = await self.llm.complete(prompt, max_tokens=20)
        
        return Improvement(
            id=generate_uuid(),
            improvement_type="alias",
            tier=1,  # Alias additions are low risk
            target=f"entity:{likely_device.strip()}",
            current_value=None,
            proposed_value=json.dumps(list(set(entity_texts))),
            rationale=f"Adding {len(set(entity_texts))} aliases for '{likely_device.strip()}' based on {len(cluster)} resolution failures",
            signal_ids=[s.id for s in cluster],
        )
    
    async def _analyze_correction_cluster(
        self,
        cluster: List[ImprovementSignal],
    ) -> Optional['Improvement']:
        """Analyze correction cluster → propose intent/pattern changes."""
        
        # This is higher risk - tier 2
        # Would need to understand what the correction was
        
        # For now, just log for human review
        return Improvement(
            id=generate_uuid(),
            improvement_type="pattern",
            tier=2,  # Requires human approval
            target="intent_classification",
            current_value=None,
            proposed_value=json.dumps([
                {"utterance": s.utterance, "correction": s.context.get("correction_text")}
                for s in cluster
            ]),
            rationale=f"User corrections suggest classification issues for {len(cluster)} utterances",
            signal_ids=[s.id for s in cluster],
        )
    
    def _cosine_similarity(self, a, b) -> float:
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


@dataclass
class Improvement:
    id: str
    improvement_type: str  # 'alias', 'exemplar', 'synonym', 'pattern', 'template'
    tier: int  # 1, 2, or 3
    target: str
    current_value: Optional[str]
    proposed_value: str
    rationale: str
    signal_ids: List[str]
    
    # Filled during validation
    shadow_test_passed: Optional[bool] = None
    shadow_test_results: Optional[dict] = None
    
    # Status tracking
    status: str = "pending"
    approved_by: Optional[str] = None
    applied_at: Optional[datetime] = None
```

---

## 5. Shadow Testing

### 5.1 Shadow Test Runner

```python
class ShadowTestRunner:
    """Test improvements against golden dataset before deployment."""
    
    def __init__(
        self,
        classifier: 'IntentClassifier',
        entity_resolver: 'HAEntityResolver',
        golden_dataset_path: str,
    ):
        self.classifier = classifier
        self.resolver = entity_resolver
        self.golden_dataset = self._load_golden_dataset(golden_dataset_path)
        
        # Minimum requirements
        self.MIN_ACCURACY = 0.95
        self.MAX_LATENCY_REGRESSION_MS = 10
        self.ZERO_REGRESSION_REQUIRED = True
    
    async def test_improvement(
        self,
        improvement: Improvement,
    ) -> Tuple[bool, dict]:
        """
        Test an improvement against golden dataset.
        
        Returns: (passed, results_dict)
        """
        
        # Get baseline metrics
        baseline = await self._run_baseline()
        
        # Apply improvement to shadow copy
        shadow_classifier = await self._create_shadow_classifier(improvement)
        
        # Run shadow tests
        shadow = await self._run_tests(shadow_classifier)
        
        # Compare
        results = {
            "baseline": baseline,
            "shadow": shadow,
            "diff": {
                "accuracy": shadow["accuracy"] - baseline["accuracy"],
                "latency_p95_ms": shadow["latency_p95_ms"] - baseline["latency_p95_ms"],
                "regressions": shadow["regressions"],
            }
        }
        
        # Determine pass/fail
        passed = (
            shadow["accuracy"] >= self.MIN_ACCURACY and
            results["diff"]["accuracy"] >= 0 and  # No accuracy regression
            results["diff"]["latency_p95_ms"] <= self.MAX_LATENCY_REGRESSION_MS and
            len(shadow["regressions"]) == 0 if self.ZERO_REGRESSION_REQUIRED else True
        )
        
        return passed, results
    
    async def _run_baseline(self) -> dict:
        """Run golden dataset with current classifier."""
        return await self._run_tests(self.classifier)
    
    async def _run_tests(self, classifier) -> dict:
        """Run golden dataset tests."""
        correct = 0
        total = 0
        latencies = []
        regressions = []
        
        for example in self.golden_dataset:
            start = time.perf_counter()
            result = await classifier.classify(example["utterance"])
            latency = (time.perf_counter() - start) * 1000
            
            latencies.append(latency)
            total += 1
            
            if result.intent == example["expected_intent"]:
                correct += 1
            else:
                regressions.append({
                    "utterance": example["utterance"],
                    "expected": example["expected_intent"],
                    "got": result.intent,
                })
        
        return {
            "accuracy": correct / total if total > 0 else 0,
            "latency_p95_ms": np.percentile(latencies, 95) if latencies else 0,
            "total": total,
            "correct": correct,
            "regressions": regressions,
        }
    
    async def _create_shadow_classifier(
        self,
        improvement: Improvement,
    ) -> 'IntentClassifier':
        """Create classifier with improvement applied."""
        
        # Clone current classifier
        shadow = self.classifier.clone()
        
        # Apply improvement based on type
        if improvement.improvement_type == "exemplar":
            intent = improvement.target.replace("intent:", "")
            new_exemplars = json.loads(improvement.proposed_value)
            await shadow.add_exemplars(intent, new_exemplars)
        
        elif improvement.improvement_type == "alias":
            entity = improvement.target.replace("entity:", "")
            new_aliases = json.loads(improvement.proposed_value)
            await shadow.resolver.add_aliases(entity, new_aliases)
        
        elif improvement.improvement_type == "synonym":
            synonyms = json.loads(improvement.proposed_value)
            await shadow.preprocessor.add_synonyms(synonyms)
        
        return shadow
    
    def _load_golden_dataset(self, path: str) -> List[dict]:
        """Load golden dataset from file."""
        with open(path) as f:
            return json.load(f)
```

### 5.2 Golden Dataset Structure

```python
# Golden dataset format: /data/golden_dataset.json
GOLDEN_DATASET_EXAMPLE = [
    {
        "id": "gd-001",
        "utterance": "turn on the kitchen lights",
        "expected_intent": "light_control",
        "expected_entities": {
            "device": "light.kitchen",
            "action": "on"
        },
        "category": "basic_command",
        "added": "2024-01-01"
    },
    {
        "id": "gd-002",
        "utterance": "what time is it",
        "expected_intent": "time_query",
        "expected_entities": {},
        "category": "basic_query",
        "added": "2024-01-01"
    },
    # ... 500+ more examples covering all intents and edge cases
]
```

---

## 6. Deployment

### 6.1 Deployment Manager

```python
class ImprovementDeployer:
    """Deploy approved improvements atomically."""
    
    def __init__(
        self,
        db: Database,
        classifier: 'IntentClassifier',
        entity_resolver: 'HAEntityResolver',
    ):
        self.db = db
        self.classifier = classifier
        self.resolver = entity_resolver
    
    async def deploy(self, improvement: Improvement) -> bool:
        """
        Deploy improvement atomically with rollback capability.
        """
        
        # Tier check
        if improvement.tier == 3:
            raise ForbiddenImprovementError("Tier 3 improvements cannot be deployed")
        
        if improvement.tier == 2 and not improvement.approved_by:
            raise ApprovalRequiredError("Tier 2 improvements require human approval")
        
        # Check shadow test passed
        if not improvement.shadow_test_passed:
            raise ValidationError("Shadow test must pass before deployment")
        
        # Create backup
        backup = await self._create_backup(improvement)
        
        try:
            # Apply atomically
            await self._apply_improvement(improvement)
            
            # Update status
            improvement.status = "applied"
            improvement.applied_at = datetime.utcnow()
            improvement.monitoring_start = datetime.utcnow()
            improvement.monitoring_end = datetime.utcnow() + timedelta(hours=24)
            
            await self._save_improvement(improvement)
            
            # Audit log
            await self._audit_log(improvement, "applied", "system")
            
            return True
        
        except Exception as e:
            # Rollback
            await self._restore_backup(backup)
            
            # Audit log
            await self._audit_log(
                improvement, 
                "apply_failed", 
                "system",
                {"error": str(e)}
            )
            
            raise
    
    async def rollback(self, improvement_id: str, reason: str) -> bool:
        """Rollback a deployed improvement."""
        
        improvement = await self._get_improvement(improvement_id)
        
        if improvement.status != "applied":
            raise InvalidStateError("Can only rollback applied improvements")
        
        # Get backup
        backup = await self._get_backup(improvement_id)
        
        if not backup:
            raise RollbackError("No backup found for improvement")
        
        # Restore
        await self._restore_backup(backup)
        
        # Update status
        improvement.status = "rolled_back"
        improvement.rolled_back_at = datetime.utcnow()
        
        await self._save_improvement(improvement)
        
        # Audit log
        await self._audit_log(
            improvement,
            "rolled_back",
            "system",
            {"reason": reason}
        )
        
        return True
    
    async def _apply_improvement(self, improvement: Improvement):
        """Apply improvement to live system."""
        
        if improvement.improvement_type == "exemplar":
            intent = improvement.target.replace("intent:", "")
            new_exemplars = json.loads(improvement.proposed_value)
            
            # Add to database
            for exemplar in new_exemplars:
                await self.db.execute(
                    """
                    INSERT INTO training_examples (utterance, intent, source)
                    VALUES (?, ?, 'self_improvement')
                    """,
                    [exemplar, intent]
                )
            
            # Reload classifier exemplars
            await self.classifier.reload_exemplars()
        
        elif improvement.improvement_type == "alias":
            entity = improvement.target.replace("entity:", "")
            new_aliases = json.loads(improvement.proposed_value)
            
            # Add to database
            for alias in new_aliases:
                await self.db.execute(
                    """
                    INSERT INTO entity_aliases (entity_id, alias, source)
                    VALUES (?, ?, 'self_improvement')
                    """,
                    [entity, alias]
                )
            
            # Reload resolver
            await self.resolver.reload_aliases()
        
        elif improvement.improvement_type == "synonym":
            synonyms = json.loads(improvement.proposed_value)
            
            # Add to database
            for word, syn_list in synonyms.items():
                for syn in syn_list:
                    await self.db.execute(
                        """
                        INSERT INTO synonyms (word, synonym, source)
                        VALUES (?, ?, 'self_improvement')
                        """,
                        [word, syn]
                    )
            
            # Reload preprocessor
            await self.classifier.preprocessor.reload_synonyms()
    
    async def _create_backup(self, improvement: Improvement) -> dict:
        """Create backup of current state."""
        backup = {
            "improvement_id": improvement.id,
            "target": improvement.target,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {}
        }
        
        if improvement.improvement_type == "exemplar":
            intent = improvement.target.replace("intent:", "")
            rows = await self.db.fetchall(
                "SELECT * FROM training_examples WHERE intent = ?",
                [intent]
            )
            backup["data"]["exemplars"] = [dict(r) for r in rows]
        
        elif improvement.improvement_type == "alias":
            entity = improvement.target.replace("entity:", "")
            rows = await self.db.fetchall(
                "SELECT * FROM entity_aliases WHERE entity_id = ?",
                [entity]
            )
            backup["data"]["aliases"] = [dict(r) for r in rows]
        
        # Store backup
        await self.db.execute(
            """
            INSERT INTO improvement_backups (improvement_id, backup_data)
            VALUES (?, ?)
            """,
            [improvement.id, json.dumps(backup)]
        )
        
        return backup
```

---

## 7. Post-Deployment Monitoring

### 7.1 Monitor

```python
class ImprovementMonitor:
    """Monitor deployed improvements for regressions."""
    
    MONITORING_WINDOW_HOURS = 24
    
    # Thresholds for automatic rollback
    ACCURACY_DROP_THRESHOLD = 0.02  # 2% accuracy drop
    LATENCY_INCREASE_THRESHOLD_MS = 50  # 50ms P95 increase
    ERROR_RATE_THRESHOLD = 0.05  # 5% error rate
    
    def __init__(
        self,
        db: Database,
        deployer: ImprovementDeployer,
        metrics_collector: 'MetricsCollector',
    ):
        self.db = db
        self.deployer = deployer
        self.metrics = metrics_collector
    
    async def check_active_improvements(self):
        """Check all improvements in monitoring window."""
        
        # Get improvements in monitoring window
        improvements = await self.db.fetchall(
            """
            SELECT * FROM improvements
            WHERE status = 'applied'
            AND monitoring_end > datetime('now')
            """
        )
        
        for row in improvements:
            improvement = self._row_to_improvement(row)
            await self._check_improvement(improvement)
    
    async def _check_improvement(self, improvement: Improvement):
        """Check a single improvement for regressions."""
        
        # Get metrics since deployment
        metrics = await self.metrics.get_metrics_since(improvement.applied_at)
        
        # Get baseline metrics (before deployment)
        baseline = await self.metrics.get_metrics_before(improvement.applied_at)
        
        # Check for regressions
        should_rollback, reason = self._check_regressions(baseline, metrics)
        
        if should_rollback:
            logger.warning(
                f"Regression detected for improvement {improvement.id}: {reason}"
            )
            
            # Automatic rollback
            await self.deployer.rollback(improvement.id, reason)
            
            # Alert
            await self._send_alert(improvement, reason)
        
        else:
            # Update monitoring results
            await self.db.execute(
                """
                UPDATE improvements
                SET monitoring_results = ?
                WHERE id = ?
                """,
                [json.dumps(metrics), improvement.id]
            )
    
    def _check_regressions(
        self,
        baseline: dict,
        current: dict,
    ) -> Tuple[bool, str]:
        """Check if current metrics indicate regression."""
        
        # Accuracy check
        accuracy_drop = baseline["accuracy"] - current["accuracy"]
        if accuracy_drop > self.ACCURACY_DROP_THRESHOLD:
            return True, f"Accuracy dropped by {accuracy_drop:.2%}"
        
        # Latency check
        latency_increase = current["latency_p95_ms"] - baseline["latency_p95_ms"]
        if latency_increase > self.LATENCY_INCREASE_THRESHOLD_MS:
            return True, f"P95 latency increased by {latency_increase:.0f}ms"
        
        # Error rate check
        if current["error_rate"] > self.ERROR_RATE_THRESHOLD:
            return True, f"Error rate at {current['error_rate']:.2%}"
        
        return False, ""
    
    async def complete_monitoring(self, improvement_id: str):
        """Mark monitoring as complete (after window passes)."""
        
        improvement = await self._get_improvement(improvement_id)
        
        if improvement.monitoring_end > datetime.utcnow():
            return  # Still in window
        
        # Final metrics check
        final_metrics = await self.metrics.get_metrics_for_period(
            improvement.applied_at,
            improvement.monitoring_end,
        )
        
        # Update improvement
        await self.db.execute(
            """
            UPDATE improvements
            SET status = 'completed',
                monitoring_results = ?
            WHERE id = ?
            """,
            [json.dumps(final_metrics), improvement_id]
        )
        
        # Audit log
        await self._audit_log(
            improvement,
            "monitoring_complete",
            "system",
            {"final_metrics": final_metrics}
        )
```

---

## 8. Scheduled Jobs

### 8.1 Job Scheduler

```python
class ImprovementScheduler:
    """Schedule periodic improvement analysis and monitoring."""
    
    def __init__(
        self,
        analyzer: ImprovementAnalyzer,
        tester: ShadowTestRunner,
        deployer: ImprovementDeployer,
        monitor: ImprovementMonitor,
    ):
        self.analyzer = analyzer
        self.tester = tester
        self.deployer = deployer
        self.monitor = monitor
    
    async def run_nightly_analysis(self):
        """
        Nightly job to analyze signals and propose improvements.
        Runs at 3 AM to minimize impact.
        """
        logger.info("Starting nightly improvement analysis")
        
        # Analyze signals
        improvements = await self.analyzer.analyze_pending_signals()
        
        logger.info(f"Generated {len(improvements)} improvement proposals")
        
        for improvement in improvements:
            # Shadow test
            passed, results = await self.tester.test_improvement(improvement)
            
            improvement.shadow_test_passed = passed
            improvement.shadow_test_results = results
            
            # Save improvement
            await self._save_improvement(improvement)
            
            if passed and improvement.tier == 1:
                # Auto-deploy tier 1
                try:
                    await self.deployer.deploy(improvement)
                    logger.info(f"Auto-deployed tier 1 improvement: {improvement.id}")
                except Exception as e:
                    logger.error(f"Failed to deploy improvement: {e}")
            
            elif passed and improvement.tier == 2:
                # Queue for human approval
                logger.info(f"Tier 2 improvement queued for approval: {improvement.id}")
    
    async def run_hourly_monitoring(self):
        """
        Hourly job to check deployed improvements.
        """
        await self.monitor.check_active_improvements()
    
    async def run_monitoring_completion(self):
        """
        Daily job to complete monitoring for improvements past window.
        """
        improvements = await self.db.fetchall(
            """
            SELECT id FROM improvements
            WHERE status = 'applied'
            AND monitoring_end < datetime('now')
            """
        )
        
        for row in improvements:
            await self.monitor.complete_monitoring(row["id"])
```

---

## 9. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── improvement/
│           ├── __init__.py
│           ├── config.py               # Thresholds, schedules
│           ├── models.py               # Improvement, ImprovementSignal
│           ├── collection/
│           │   ├── __init__.py
│           │   └── collector.py        # SignalCollector
│           ├── analysis/
│           │   ├── __init__.py
│           │   └── analyzer.py         # ImprovementAnalyzer
│           ├── testing/
│           │   ├── __init__.py
│           │   └── shadow.py           # ShadowTestRunner
│           ├── deployment/
│           │   ├── __init__.py
│           │   └── deployer.py         # ImprovementDeployer
│           ├── monitoring/
│           │   ├── __init__.py
│           │   └── monitor.py          # ImprovementMonitor
│           └── scheduler.py            # ImprovementScheduler
├── data/
│   └── golden_dataset.json             # 500+ labeled test cases
└── tests/
    └── improvement/
        ├── test_collector.py
        ├── test_analyzer.py
        ├── test_shadow.py
        └── test_deployer.py
```

---

## 10. Implementation Checklist

### Signal Collection

- [ ] LLM fallback signal recording
- [ ] User correction detection
- [ ] Entity failure recording
- [ ] Low-confidence recording
- [ ] Signal persistence

### Analysis

- [ ] Signal clustering by embedding
- [ ] LLM fallback → exemplar proposals
- [ ] Entity failure → alias proposals
- [ ] Correction → pattern proposals (tier 2)
- [ ] Tier assignment logic

### Shadow Testing

- [ ] Golden dataset (500+ examples)
- [ ] Shadow classifier creation
- [ ] Metrics comparison
- [ ] Pass/fail determination
- [ ] Zero-regression enforcement

### Deployment

- [ ] Tier checking
- [ ] Approval requirement for tier 2
- [ ] Atomic application
- [ ] Backup creation
- [ ] Rollback mechanism
- [ ] Audit logging

### Monitoring

- [ ] 24-hour monitoring window
- [ ] Automatic regression detection
- [ ] Automatic rollback trigger
- [ ] Monitoring completion

### Scheduled Jobs

- [ ] Nightly analysis job
- [ ] Hourly monitoring job
- [ ] Job scheduling infrastructure

### Validation

- [ ] Tier 1 auto-deploys without incident
- [ ] Tier 2 requires human approval
- [ ] Tier 3 is blocked
- [ ] Rollback works correctly
- [ ] No production regressions from self-improvement

### Acceptance Criteria

1. **Tier 1 improvements deploy automatically** after passing shadow tests
2. **Tier 2 improvements require human approval** via dashboard
3. **Tier 3 modifications are impossible** (code/schema/API)
4. **Automatic rollback within 1 hour** of detected regression
5. **Zero incidents from self-improvement** (V1 failure mode prevented)
6. **Full audit trail** of all improvements

---

## 11. Handoff Notes for Implementation Agent

### Critical Points

1. **NEVER modify code.** All improvements must be data changes (exemplars, aliases, synonyms). If you find yourself generating code, STOP.

2. **Shadow testing is mandatory.** No improvement deploys without passing the golden dataset.

3. **Golden dataset is sacred.** It must cover all intents, edge cases, and regression scenarios. Start with 500+ examples.

4. **Rollback must be instant.** If metrics degrade, rollback happens automatically—no waiting for human.

5. **Audit everything.** Every signal, every proposal, every deployment, every rollback.

### Common Pitfalls

- Treating "low confidence" as always needing improvement (some queries are genuinely ambiguous)
- Clustering signals too aggressively (false positives on similar-but-different utterances)
- Not including the actual correction in correction signal analysis
- Deploying improvements during peak hours (do it at 3 AM)
- Not monitoring long enough (24 hours catches delayed issues)

### V1 Failure Prevention Checklist

Before ANY change deployment:
- [ ] Is this a data-only change? (No code modification)
- [ ] Did it pass shadow testing? (Accuracy ≥95%, zero regressions)
- [ ] Is the tier appropriate? (Tier 1 = data, Tier 2 = patterns, Tier 3 = forbidden)
- [ ] Is backup created? (Can rollback instantly)
- [ ] Is monitoring active? (24-hour window)

---

**End of Area 08: Self-Improvement Pipeline**
