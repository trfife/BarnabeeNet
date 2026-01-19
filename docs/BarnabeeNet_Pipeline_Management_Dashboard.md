# BarnabeeNet Pipeline Management Dashboard

**Document Version:** 1.0  
**Date:** January 19, 2026  
**Author:** Thom Fife  
**Status:** 📋 Implementation Specification  
**Purpose:** Complete specification for the Intent Pipeline Management Dashboard with AI-assisted correction  

**Project plan:** This work is **Phase 7** in `barnabeenet-project-log.md`, to start **after** Home Assistant connection work is complete. See CONTEXT.md Next Steps.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architectural Philosophy](#2-architectural-philosophy)
3. [The Decision Registry](#3-the-decision-registry)
4. [Signal & Trace Architecture](#4-signal--trace-architecture)
5. [Dashboard UI Specification](#5-dashboard-ui-specification)
6. [Pipeline Timeline View](#6-pipeline-timeline-view)
7. [AI Correction Assistant](#7-ai-correction-assistant)
8. [Editable Logic System](#8-editable-logic-system)
9. [Data Models](#9-data-models)
10. [API Specification](#10-api-specification)
11. [Database Schema](#11-database-schema)
12. [Implementation Phases](#12-implementation-phases)
13. [Code Examples](#13-code-examples)

---

## 1. Executive Summary

### 1.1 The Core Problem

BarnabeeNet makes hundreds of decisions per request: which patterns to check, which agent to route to, which entities to resolve, which model to call, what temperature to use, etc. Currently, these decisions are embedded in code and invisible to the user.

**The Goal:** Make every decision point visible, traceable, and editable—without requiring code changes.

### 1.2 The Solution: Decision-Centric Architecture

Every logical choice in BarnabeeNet becomes a **registered decision point** that:
- Logs its inputs, logic, and outputs
- Can be viewed in the dashboard timeline
- Can be overridden or modified through the UI
- Provides AI with full context for suggesting fixes

### 1.3 Key Principles

| Principle | Implementation |
|-----------|----------------|
| **Every decision is logged** | Decision Registry captures all logic evaluations |
| **Every decision is editable** | Logic stored as data, not just code |
| **Full context for AI** | AI assistant can see code, config, and execution history |
| **No code deploys for fixes** | Hot-reload patterns, prompts, and overrides |
| **Regression protection** | Test changes against historical requests before applying |

---

## 2. Architectural Philosophy

### 2.1 From Code-Driven to Data-Driven Logic

**Before (Code-Driven):**
```python
# Logic embedded in code - invisible to users
if re.match(r"^(turn|switch) (on|off) .*$", text):
    return IntentCategory.ACTION
```

**After (Data-Driven with Decision Registry):**
```python
# Logic is data that can be viewed and edited
decision = await decision_registry.evaluate(
    decision_type="pattern_match",
    decision_id="action.switch_control",
    inputs={"text": text},
    logic_ref="patterns.action.switch_control",  # Points to editable config
)
# Decision is automatically logged with full context
```

### 2.2 The Decision Registry Concept

Every logical branch in BarnabeeNet registers with a central Decision Registry:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DECISION REGISTRY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Decision Point          │ Logic Source           │ Editable?  │ Override?  │
│  ────────────────────────┼────────────────────────┼────────────┼─────────── │
│  meta.pattern_match      │ config/patterns.yaml   │ ✅ Yes     │ ✅ Yes     │
│  meta.llm_classify       │ prompts/meta/class.j2  │ ✅ Yes     │ ✅ Yes     │
│  meta.route_to_agent     │ config/routing.yaml    │ ✅ Yes     │ ✅ Yes     │
│  action.resolve_entity   │ code + config/aliases  │ ⚠️ Partial │ ✅ Yes     │
│  action.select_service   │ prompts/action/exec.j2 │ ✅ Yes     │ ✅ Yes     │
│  action.call_ha          │ code (HA client)       │ ❌ No      │ ✅ Yes     │
│  interaction.select_model│ config/models.yaml     │ ✅ Yes     │ ✅ Yes     │
│  interaction.build_prompt│ prompts/interact/*.j2  │ ✅ Yes     │ ✅ Yes     │
│  tts.select_voice        │ config/voices.yaml     │ ✅ Yes     │ ✅ Yes     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Trace Hierarchy

Every request generates a complete trace with nested decision points:

```
Request Trace (trace_id: tr_abc123)
├── Input Processing
│   ├── Decision: stt.transcribe
│   │   └── Model: parakeet, Confidence: 0.94
│   └── Decision: speaker.identify
│       └── Result: Thom (from HA context)
│
├── Meta Agent
│   ├── Decision: meta.check_emergency_patterns
│   │   └── Patterns checked: 4, Match: None
│   ├── Decision: meta.check_instant_patterns
│   │   └── Patterns checked: 7, Match: None
│   ├── Decision: meta.check_action_patterns
│   │   └── Patterns checked: 8, Match: "switch_control" ✅
│   ├── Decision: meta.evaluate_context
│   │   └── Tone: neutral, Urgency: low
│   └── Decision: meta.route
│       └── Target: action_agent, Confidence: 0.95
│
├── Action Agent
│   ├── Decision: action.resolve_entities
│   │   ├── Input: "the office light"
│   │   ├── Candidates: [light.office_light, light.office_desk]
│   │   └── Selected: light.office_light (score: 0.92)
│   ├── Decision: action.determine_service
│   │   └── Service: light.turn_off
│   ├── Decision: action.call_ha
│   │   └── Result: SUCCESS, Latency: 23ms
│   └── Decision: action.generate_response
│       └── Text: "Done, I've turned off the office light."
│
└── Output
    └── Decision: tts.synthesize
        └── Voice: bm_fable, Duration: 1.2s
```

---

## 3. The Decision Registry

### 3.1 Core Decision Registry Class

```python
# core/decision_registry.py
"""
Decision Registry - The foundation of observable, editable logic.

Every logical branch in BarnabeeNet registers here. This enables:
1. Complete tracing of all decisions
2. UI-based editing of logic
3. AI-assisted corrections with full context
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Callable, TypeVar, Generic
import structlog

logger = structlog.get_logger()

T = TypeVar('T')


class DecisionType(Enum):
    """Categories of decisions in BarnabeeNet."""
    PATTERN_MATCH = "pattern_match"
    LLM_CALL = "llm_call"
    ENTITY_RESOLUTION = "entity_resolution"
    ROUTING = "routing"
    SERVICE_CALL = "service_call"
    OVERRIDE_CHECK = "override_check"
    THRESHOLD_CHECK = "threshold_check"
    MODEL_SELECTION = "model_selection"
    PROMPT_RENDER = "prompt_render"
    RESPONSE_GENERATION = "response_generation"


class DecisionOutcome(Enum):
    """Possible outcomes of a decision."""
    MATCH = "match"
    NO_MATCH = "no_match"
    SELECTED = "selected"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    ERROR = "error"
    OVERRIDDEN = "overridden"


@dataclass
class DecisionInput:
    """Inputs to a decision point."""
    primary: Any  # The main input (e.g., text for pattern match)
    context: dict[str, Any] = field(default_factory=dict)  # Additional context
    

@dataclass
class DecisionLogic:
    """The logic that was applied to make the decision."""
    logic_type: str  # "pattern", "llm", "threshold", "lookup", etc.
    logic_source: str  # File path or config key where logic is defined
    logic_content: str | dict | None  # The actual logic (pattern, prompt, etc.)
    logic_version: str | None = None  # Version hash for tracking changes
    is_editable: bool = True  # Can this logic be edited via UI?
    

@dataclass
class DecisionResult:
    """The result of a decision."""
    outcome: DecisionOutcome
    value: Any  # The actual result value
    confidence: float = 1.0
    alternatives: list[dict[str, Any]] = field(default_factory=list)  # Other options considered
    explanation: str | None = None  # Human-readable explanation
    

@dataclass
class DecisionRecord:
    """Complete record of a decision for logging and analysis."""
    
    # Identification
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None
    parent_decision_id: str | None = None
    
    # Classification
    decision_type: DecisionType = DecisionType.PATTERN_MATCH
    decision_name: str = ""  # e.g., "meta.check_action_patterns"
    component: str = ""  # e.g., "meta_agent", "action_agent"
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float | None = None
    
    # The decision details
    inputs: DecisionInput | None = None
    logic: DecisionLogic | None = None
    result: DecisionResult | None = None
    
    # For nested decisions
    child_decisions: list[str] = field(default_factory=list)
    
    # Error tracking
    error: str | None = None
    error_type: str | None = None
    
    def complete(self, result: DecisionResult) -> None:
        """Mark decision as complete with result."""
        self.completed_at = datetime.now(UTC)
        self.result = result
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000


class DecisionRegistry:
    """
    Central registry for all decision points in BarnabeeNet.
    
    Usage:
        registry = DecisionRegistry()
        
        async with registry.decision(
            name="meta.check_action_patterns",
            decision_type=DecisionType.PATTERN_MATCH,
            trace_id=trace_id,
        ) as decision:
            decision.set_inputs(text=user_input)
            decision.set_logic(
                logic_type="pattern",
                logic_source="config/patterns.yaml#action",
                logic_content=pattern_list,
            )
            
            # Do the actual work
            match = check_patterns(user_input, patterns)
            
            decision.set_result(
                outcome=DecisionOutcome.MATCH if match else DecisionOutcome.NO_MATCH,
                value=match,
                confidence=0.95,
                alternatives=other_near_matches,
            )
    """
    
    def __init__(self):
        self._decisions: dict[str, DecisionRecord] = {}
        self._trace_decisions: dict[str, list[str]] = {}  # trace_id -> decision_ids
        self._decision_stack: list[str] = []  # For nested decisions
        self._logger: DecisionLogger | None = None
        self._logic_registry: LogicRegistry | None = None
        
    def set_logger(self, logger: DecisionLogger) -> None:
        """Set the logger for persisting decisions."""
        self._logger = logger
        
    def set_logic_registry(self, registry: LogicRegistry) -> None:
        """Set the logic registry for retrieving editable logic."""
        self._logic_registry = registry
    
    def decision(
        self,
        name: str,
        decision_type: DecisionType,
        trace_id: str | None = None,
        component: str | None = None,
    ) -> DecisionContext:
        """Create a decision context manager."""
        return DecisionContext(
            registry=self,
            name=name,
            decision_type=decision_type,
            trace_id=trace_id,
            component=component,
        )
    
    async def record_decision(self, record: DecisionRecord) -> None:
        """Record a completed decision."""
        self._decisions[record.decision_id] = record
        
        if record.trace_id:
            if record.trace_id not in self._trace_decisions:
                self._trace_decisions[record.trace_id] = []
            self._trace_decisions[record.trace_id].append(record.decision_id)
        
        # Persist to storage
        if self._logger:
            await self._logger.log_decision(record)
    
    async def get_trace_decisions(self, trace_id: str) -> list[DecisionRecord]:
        """Get all decisions for a trace."""
        if self._logger:
            return await self._logger.get_trace_decisions(trace_id)
        
        decision_ids = self._trace_decisions.get(trace_id, [])
        return [self._decisions[did] for did in decision_ids if did in self._decisions]
    
    async def get_logic_for_decision(self, decision_name: str) -> dict[str, Any] | None:
        """Get the editable logic configuration for a decision type."""
        if self._logic_registry:
            return await self._logic_registry.get_logic(decision_name)
        return None
    
    async def update_logic(
        self,
        decision_name: str,
        new_logic: dict[str, Any],
        reason: str,
        user: str,
    ) -> bool:
        """Update the logic for a decision type (hot-reload)."""
        if self._logic_registry:
            return await self._logic_registry.update_logic(
                decision_name=decision_name,
                new_logic=new_logic,
                reason=reason,
                user=user,
            )
        return False


class DecisionContext:
    """Context manager for recording a decision."""
    
    def __init__(
        self,
        registry: DecisionRegistry,
        name: str,
        decision_type: DecisionType,
        trace_id: str | None,
        component: str | None,
    ):
        self._registry = registry
        self._record = DecisionRecord(
            decision_name=name,
            decision_type=decision_type,
            trace_id=trace_id,
            component=component or name.split(".")[0],
        )
        self._inputs: dict[str, Any] = {}
        self._context: dict[str, Any] = {}
        self._logic_type: str | None = None
        self._logic_source: str | None = None
        self._logic_content: Any = None
        
    async def __aenter__(self) -> DecisionContext:
        """Enter decision context."""
        # Set parent if there's a current decision on the stack
        if self._registry._decision_stack:
            parent_id = self._registry._decision_stack[-1]
            self._record.parent_decision_id = parent_id
            # Add this as child of parent
            if parent_id in self._registry._decisions:
                self._registry._decisions[parent_id].child_decisions.append(
                    self._record.decision_id
                )
        
        self._registry._decision_stack.append(self._record.decision_id)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit decision context and record the decision."""
        self._registry._decision_stack.pop()
        
        if exc_type:
            self._record.error = str(exc_val)
            self._record.error_type = exc_type.__name__
            if not self._record.result:
                self._record.result = DecisionResult(
                    outcome=DecisionOutcome.ERROR,
                    value=None,
                    explanation=str(exc_val),
                )
        
        # Build the inputs
        self._record.inputs = DecisionInput(
            primary=self._inputs.get("primary"),
            context=self._context,
        )
        
        # Build the logic record
        if self._logic_source:
            self._record.logic = DecisionLogic(
                logic_type=self._logic_type or "unknown",
                logic_source=self._logic_source,
                logic_content=self._logic_content,
            )
        
        self._record.complete(self._record.result or DecisionResult(
            outcome=DecisionOutcome.SKIPPED,
            value=None,
        ))
        
        await self._registry.record_decision(self._record)
    
    def set_inputs(self, primary: Any = None, **context) -> None:
        """Set the inputs to this decision."""
        if primary is not None:
            self._inputs["primary"] = primary
        self._context.update(context)
    
    def set_logic(
        self,
        logic_type: str,
        logic_source: str,
        logic_content: Any = None,
    ) -> None:
        """Set the logic being applied."""
        self._logic_type = logic_type
        self._logic_source = logic_source
        self._logic_content = logic_content
    
    def set_result(
        self,
        outcome: DecisionOutcome,
        value: Any,
        confidence: float = 1.0,
        alternatives: list[dict[str, Any]] | None = None,
        explanation: str | None = None,
    ) -> None:
        """Set the result of this decision."""
        self._record.result = DecisionResult(
            outcome=outcome,
            value=value,
            confidence=confidence,
            alternatives=alternatives or [],
            explanation=explanation,
        )
    
    @property
    def decision_id(self) -> str:
        """Get the decision ID."""
        return self._record.decision_id
```

### 3.2 Logic Registry (Editable Logic Storage)

```python
# core/logic_registry.py
"""
Logic Registry - Storage and management of editable logic.

All decision logic that can be edited via the dashboard is stored here.
This includes patterns, prompts, thresholds, routing rules, and overrides.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import yaml
import structlog
from jinja2 import Environment, FileSystemLoader

logger = structlog.get_logger()


@dataclass
class LogicDefinition:
    """Definition of a piece of editable logic."""
    
    logic_id: str  # e.g., "patterns.action.switch_control"
    logic_type: str  # "pattern", "prompt", "threshold", "routing", "override"
    
    # Where this logic is stored
    storage_type: str  # "yaml", "jinja2", "json", "python"
    storage_path: str  # File path or Redis key
    storage_key: str | None = None  # Key within the file (for YAML/JSON)
    
    # The actual content
    content: Any = None
    content_hash: str | None = None  # For version tracking
    
    # Metadata
    description: str = ""
    editable: bool = True
    requires_restart: bool = False  # Does changing this require restart?
    
    # History
    last_modified: datetime | None = None
    modified_by: str | None = None
    modification_reason: str | None = None


@dataclass
class LogicChange:
    """Record of a change to logic."""
    
    change_id: str
    logic_id: str
    timestamp: datetime
    user: str
    reason: str
    
    before_content: Any
    before_hash: str
    after_content: Any
    after_hash: str
    
    # Validation
    tested_against_traces: list[str] = field(default_factory=list)
    test_results: dict[str, bool] = field(default_factory=dict)
    
    # Status
    status: str = "pending"  # "pending", "applied", "reverted"
    applied_at: datetime | None = None
    reverted_at: datetime | None = None
    revert_reason: str | None = None


class LogicRegistry:
    """
    Registry for all editable logic in BarnabeeNet.
    
    This is the source of truth for:
    - Pattern definitions
    - Prompt templates
    - Routing rules
    - Override configurations
    - Model selection rules
    - Threshold values
    """
    
    def __init__(
        self,
        config_dir: Path,
        prompts_dir: Path,
        redis_client: Any = None,
    ):
        self.config_dir = config_dir
        self.prompts_dir = prompts_dir
        self.redis = redis_client
        
        self._logic_cache: dict[str, LogicDefinition] = {}
        self._change_history: list[LogicChange] = []
        
        # Jinja2 environment for prompt templates
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            autoescape=False,
        )
    
    async def initialize(self) -> None:
        """Load all logic definitions on startup."""
        await self._load_patterns()
        await self._load_routing_rules()
        await self._load_overrides()
        await self._load_model_config()
        await self._load_prompt_registry()
        
        logger.info(
            "Logic registry initialized",
            total_definitions=len(self._logic_cache),
        )
    
    async def _load_patterns(self) -> None:
        """Load pattern definitions from config."""
        patterns_file = self.config_dir / "patterns.yaml"
        if patterns_file.exists():
            with open(patterns_file) as f:
                patterns_config = yaml.safe_load(f)
            
            for group_name, patterns in patterns_config.get("pattern_groups", {}).items():
                for i, pattern_def in enumerate(patterns):
                    logic_id = f"patterns.{group_name}.{pattern_def.get('name', i)}"
                    self._logic_cache[logic_id] = LogicDefinition(
                        logic_id=logic_id,
                        logic_type="pattern",
                        storage_type="yaml",
                        storage_path=str(patterns_file),
                        storage_key=f"pattern_groups.{group_name}[{i}]",
                        content=pattern_def,
                        content_hash=self._hash_content(pattern_def),
                        description=pattern_def.get("description", ""),
                        editable=True,
                        requires_restart=False,
                    )
    
    async def _load_routing_rules(self) -> None:
        """Load routing rules from config."""
        routing_file = self.config_dir / "routing.yaml"
        if routing_file.exists():
            with open(routing_file) as f:
                routing_config = yaml.safe_load(f)
            
            for rule_name, rule_def in routing_config.get("rules", {}).items():
                logic_id = f"routing.{rule_name}"
                self._logic_cache[logic_id] = LogicDefinition(
                    logic_id=logic_id,
                    logic_type="routing",
                    storage_type="yaml",
                    storage_path=str(routing_file),
                    storage_key=f"rules.{rule_name}",
                    content=rule_def,
                    content_hash=self._hash_content(rule_def),
                    description=rule_def.get("description", ""),
                    editable=True,
                    requires_restart=False,
                )
    
    async def _load_overrides(self) -> None:
        """Load override rules from config."""
        overrides_file = self.config_dir / "overrides.yaml"
        if overrides_file.exists():
            with open(overrides_file) as f:
                overrides_config = yaml.safe_load(f)
            
            for override_name, override_def in overrides_config.get("overrides", {}).items():
                logic_id = f"overrides.{override_name}"
                self._logic_cache[logic_id] = LogicDefinition(
                    logic_id=logic_id,
                    logic_type="override",
                    storage_type="yaml",
                    storage_path=str(overrides_file),
                    storage_key=f"overrides.{override_name}",
                    content=override_def,
                    content_hash=self._hash_content(override_def),
                    description=override_def.get("description", ""),
                    editable=True,
                    requires_restart=False,
                )
    
    async def _load_model_config(self) -> None:
        """Load model selection configuration."""
        models_file = self.config_dir / "models.yaml"
        if models_file.exists():
            with open(models_file) as f:
                models_config = yaml.safe_load(f)
            
            for agent_name, model_def in models_config.get("agents", {}).items():
                logic_id = f"models.{agent_name}"
                self._logic_cache[logic_id] = LogicDefinition(
                    logic_id=logic_id,
                    logic_type="model_selection",
                    storage_type="yaml",
                    storage_path=str(models_file),
                    storage_key=f"agents.{agent_name}",
                    content=model_def,
                    content_hash=self._hash_content(model_def),
                    description=f"Model configuration for {agent_name}",
                    editable=True,
                    requires_restart=False,
                )
    
    async def _load_prompt_registry(self) -> None:
        """Register all prompt templates."""
        for prompt_file in self.prompts_dir.rglob("*.j2"):
            rel_path = prompt_file.relative_to(self.prompts_dir)
            logic_id = f"prompts.{str(rel_path).replace('/', '.').replace('.j2', '')}"
            
            with open(prompt_file) as f:
                content = f.read()
            
            self._logic_cache[logic_id] = LogicDefinition(
                logic_id=logic_id,
                logic_type="prompt",
                storage_type="jinja2",
                storage_path=str(prompt_file),
                content=content,
                content_hash=self._hash_content(content),
                description=f"Prompt template: {rel_path}",
                editable=True,
                requires_restart=False,
            )
    
    def _hash_content(self, content: Any) -> str:
        """Generate hash of content for version tracking."""
        if isinstance(content, str):
            content_str = content
        else:
            content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    async def get_logic(self, logic_id: str) -> LogicDefinition | None:
        """Get a logic definition by ID."""
        return self._logic_cache.get(logic_id)
    
    async def get_all_logic(self, logic_type: str | None = None) -> list[LogicDefinition]:
        """Get all logic definitions, optionally filtered by type."""
        if logic_type:
            return [
                logic for logic in self._logic_cache.values()
                if logic.logic_type == logic_type
            ]
        return list(self._logic_cache.values())
    
    async def update_logic(
        self,
        logic_id: str,
        new_content: Any,
        reason: str,
        user: str,
    ) -> LogicChange:
        """Update a logic definition."""
        logic = self._logic_cache.get(logic_id)
        if not logic:
            raise ValueError(f"Logic not found: {logic_id}")
        
        if not logic.editable:
            raise ValueError(f"Logic is not editable: {logic_id}")
        
        # Create change record
        change = LogicChange(
            change_id=str(uuid.uuid4()),
            logic_id=logic_id,
            timestamp=datetime.now(UTC),
            user=user,
            reason=reason,
            before_content=logic.content,
            before_hash=logic.content_hash,
            after_content=new_content,
            after_hash=self._hash_content(new_content),
        )
        
        # Update the logic
        logic.content = new_content
        logic.content_hash = change.after_hash
        logic.last_modified = change.timestamp
        logic.modified_by = user
        logic.modification_reason = reason
        
        # Persist to storage
        await self._persist_logic(logic)
        
        # Record the change
        self._change_history.append(change)
        change.status = "applied"
        change.applied_at = datetime.now(UTC)
        
        # Trigger hot-reload if needed
        await self._trigger_reload(logic)
        
        logger.info(
            "Logic updated",
            logic_id=logic_id,
            change_id=change.change_id,
            user=user,
        )
        
        return change
    
    async def _persist_logic(self, logic: LogicDefinition) -> None:
        """Persist logic changes to storage."""
        if logic.storage_type == "yaml":
            await self._persist_yaml_logic(logic)
        elif logic.storage_type == "jinja2":
            await self._persist_jinja_logic(logic)
        elif logic.storage_type == "json":
            await self._persist_json_logic(logic)
    
    async def _persist_yaml_logic(self, logic: LogicDefinition) -> None:
        """Persist changes to a YAML file."""
        file_path = Path(logic.storage_path)
        
        with open(file_path) as f:
            full_config = yaml.safe_load(f)
        
        # Navigate to the key and update
        keys = logic.storage_key.split(".")
        target = full_config
        for key in keys[:-1]:
            if "[" in key:
                # Handle array index
                name, idx = key.rstrip("]").split("[")
                target = target[name][int(idx)]
            else:
                target = target[key]
        
        final_key = keys[-1]
        if "[" in final_key:
            name, idx = final_key.rstrip("]").split("[")
            target[name][int(idx)] = logic.content
        else:
            target[final_key] = logic.content
        
        with open(file_path, "w") as f:
            yaml.dump(full_config, f, default_flow_style=False)
    
    async def _persist_jinja_logic(self, logic: LogicDefinition) -> None:
        """Persist changes to a Jinja2 template file."""
        with open(logic.storage_path, "w") as f:
            f.write(logic.content)
    
    async def _trigger_reload(self, logic: LogicDefinition) -> None:
        """Trigger hot-reload for the changed logic."""
        # Publish reload event to Redis for all workers to pick up
        if self.redis:
            await self.redis.publish(
                "barnabeenet:logic_reload",
                json.dumps({
                    "logic_id": logic.logic_id,
                    "logic_type": logic.logic_type,
                    "hash": logic.content_hash,
                }),
            )
    
    async def revert_change(
        self,
        change_id: str,
        reason: str,
        user: str,
    ) -> LogicChange:
        """Revert a previous change."""
        change = next(
            (c for c in self._change_history if c.change_id == change_id),
            None,
        )
        if not change:
            raise ValueError(f"Change not found: {change_id}")
        
        # Apply the revert
        await self.update_logic(
            logic_id=change.logic_id,
            new_content=change.before_content,
            reason=f"Revert: {reason}",
            user=user,
        )
        
        change.status = "reverted"
        change.reverted_at = datetime.now(UTC)
        change.revert_reason = reason
        
        return change
```

---

## 4. Signal & Trace Architecture

### 4.1 Enhanced Trace Model

```python
# models/traces.py
"""
Enhanced trace models for complete request visibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TraceStatus(Enum):
    """Status of a trace."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class RequestTrace:
    """
    Complete trace of a request through the BarnabeeNet pipeline.
    
    This is the top-level container that holds all decisions made
    during processing of a single user request.
    """
    
    # Identification
    trace_id: str
    conversation_id: str | None = None
    
    # Input
    input_type: str = "voice"  # "voice", "text", "gesture"
    input_raw: bytes | None = None  # Raw audio if applicable
    input_text: str = ""
    input_timestamp: datetime | None = None
    
    # Speaker & Context
    speaker_id: str | None = None
    speaker_name: str | None = None
    speaker_confidence: float = 0.0
    room: str | None = None
    device_id: str | None = None
    
    # Processing Summary
    status: TraceStatus = TraceStatus.IN_PROGRESS
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_duration_ms: float | None = None
    
    # Classification Results (from Meta Agent)
    intent: str | None = None
    intent_confidence: float = 0.0
    sub_category: str | None = None
    emotional_tone: str | None = None
    urgency_level: str | None = None
    
    # Routing
    routed_to_agent: str | None = None
    routing_reason: str | None = None
    
    # Agent Processing
    agent_used: str | None = None
    agent_response: str | None = None
    agent_latency_ms: float | None = None
    
    # Actions Taken
    ha_actions: list[dict[str, Any]] = field(default_factory=list)
    
    # Output
    response_text: str = ""
    response_audio_url: str | None = None
    tts_voice: str | None = None
    tts_duration_ms: float | None = None
    
    # Costs
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    
    # Decision Trail (ordered list of decision IDs)
    decision_ids: list[str] = field(default_factory=list)
    
    # Error Information
    error: str | None = None
    error_type: str | None = None
    error_decision_id: str | None = None  # Which decision failed
    
    # User Feedback
    user_rating: int | None = None  # 1-5 stars
    user_feedback: str | None = None
    marked_as_wrong: bool = False
    correction_id: str | None = None  # Link to correction if marked wrong


@dataclass
class TraceListItem:
    """Summary view of a trace for list display."""
    
    trace_id: str
    timestamp: datetime
    input_preview: str  # First 100 chars
    response_preview: str  # First 100 chars
    
    intent: str | None
    agent_used: str | None
    status: TraceStatus
    
    total_duration_ms: float | None
    decision_count: int
    llm_call_count: int
    
    marked_as_wrong: bool
    has_correction: bool


@dataclass
class DecisionTreeNode:
    """
    Node in the decision tree for visualization.
    
    Represents a single decision with its children.
    """
    
    decision_id: str
    decision_name: str
    decision_type: str
    component: str
    
    # Timing
    started_at: datetime
    duration_ms: float
    
    # Summary
    outcome: str
    outcome_value: str | None  # Simplified string representation
    confidence: float
    
    # For display
    icon: str  # Emoji for UI
    color: str  # Color code for UI
    
    # Expandable details
    inputs_summary: str
    logic_summary: str
    result_summary: str
    
    # Full details (for expansion)
    inputs_full: dict[str, Any]
    logic_full: dict[str, Any]
    result_full: dict[str, Any]
    
    # Children
    children: list[DecisionTreeNode] = field(default_factory=list)
    
    # Editability
    is_logic_editable: bool = False
    logic_id: str | None = None  # Reference to LogicRegistry
```

### 4.2 Decision Logger

```python
# services/decision_logger.py
"""
Decision Logger - Persists decisions to Redis for dashboard access.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
import structlog

from barnabeenet.core.decision_registry import DecisionRecord
from barnabeenet.models.traces import RequestTrace, TraceListItem

logger = structlog.get_logger()


class DecisionLogger:
    """
    Logs decisions and traces to Redis for dashboard consumption.
    
    Storage structure:
    - barnabeenet:traces:{trace_id} -> RequestTrace (hash)
    - barnabeenet:traces:list -> Sorted set of trace_ids by timestamp
    - barnabeenet:decisions:{decision_id} -> DecisionRecord (hash)
    - barnabeenet:trace_decisions:{trace_id} -> List of decision_ids
    - barnabeenet:wrong_traces -> Set of trace_ids marked as wrong
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        retention_days: int = 30,
    ):
        self.redis = redis_client
        self.retention_days = retention_days
        
    # =========================================================================
    # TRACE OPERATIONS
    # =========================================================================
    
    async def create_trace(self, trace: RequestTrace) -> None:
        """Create a new trace record."""
        key = f"barnabeenet:traces:{trace.trace_id}"
        
        # Serialize trace to hash
        trace_data = self._serialize_trace(trace)
        await self.redis.hset(key, mapping=trace_data)
        
        # Add to sorted set for listing
        timestamp = trace.started_at.timestamp() if trace.started_at else datetime.now().timestamp()
        await self.redis.zadd("barnabeenet:traces:list", {trace.trace_id: timestamp})
        
        # Set expiration
        await self.redis.expire(key, timedelta(days=self.retention_days))
    
    async def update_trace(self, trace: RequestTrace) -> None:
        """Update an existing trace record."""
        key = f"barnabeenet:traces:{trace.trace_id}"
        trace_data = self._serialize_trace(trace)
        await self.redis.hset(key, mapping=trace_data)
    
    async def get_trace(self, trace_id: str) -> RequestTrace | None:
        """Get a trace by ID."""
        key = f"barnabeenet:traces:{trace_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
        return self._deserialize_trace(data)
    
    async def get_recent_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        agent: str | None = None,
        speaker: str | None = None,
        room: str | None = None,
        marked_wrong: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TraceListItem]:
        """Get recent traces with filtering."""
        # Get trace IDs from sorted set
        if start_time and end_time:
            trace_ids = await self.redis.zrangebyscore(
                "barnabeenet:traces:list",
                min=start_time.timestamp(),
                max=end_time.timestamp(),
                start=offset,
                num=limit * 2,  # Fetch extra for filtering
            )
        else:
            trace_ids = await self.redis.zrevrange(
                "barnabeenet:traces:list",
                start=offset,
                end=offset + limit * 2 - 1,
            )
        
        # Fetch and filter traces
        results = []
        for trace_id in trace_ids:
            if len(results) >= limit:
                break
                
            trace = await self.get_trace(trace_id)
            if not trace:
                continue
            
            # Apply filters
            if status and trace.status.value != status:
                continue
            if agent and trace.agent_used != agent:
                continue
            if speaker and trace.speaker_id != speaker:
                continue
            if room and trace.room != room:
                continue
            if marked_wrong is not None and trace.marked_as_wrong != marked_wrong:
                continue
            
            # Convert to list item
            results.append(TraceListItem(
                trace_id=trace.trace_id,
                timestamp=trace.started_at or datetime.now(),
                input_preview=trace.input_text[:100] if trace.input_text else "",
                response_preview=trace.response_text[:100] if trace.response_text else "",
                intent=trace.intent,
                agent_used=trace.agent_used,
                status=trace.status,
                total_duration_ms=trace.total_duration_ms,
                decision_count=len(trace.decision_ids),
                llm_call_count=trace.total_llm_calls,
                marked_as_wrong=trace.marked_as_wrong,
                has_correction=trace.correction_id is not None,
            ))
        
        return results
    
    # =========================================================================
    # DECISION OPERATIONS
    # =========================================================================
    
    async def log_decision(self, decision: DecisionRecord) -> None:
        """Log a decision record."""
        key = f"barnabeenet:decisions:{decision.decision_id}"
        
        # Serialize decision
        decision_data = self._serialize_decision(decision)
        await self.redis.hset(key, mapping=decision_data)
        
        # Link to trace
        if decision.trace_id:
            await self.redis.rpush(
                f"barnabeenet:trace_decisions:{decision.trace_id}",
                decision.decision_id,
            )
            
            # Update trace's decision list
            trace = await self.get_trace(decision.trace_id)
            if trace:
                trace.decision_ids.append(decision.decision_id)
                await self.update_trace(trace)
        
        # Set expiration
        await self.redis.expire(key, timedelta(days=self.retention_days))
    
    async def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Get a decision by ID."""
        key = f"barnabeenet:decisions:{decision_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
        return self._deserialize_decision(data)
    
    async def get_trace_decisions(self, trace_id: str) -> list[DecisionRecord]:
        """Get all decisions for a trace in order."""
        decision_ids = await self.redis.lrange(
            f"barnabeenet:trace_decisions:{trace_id}",
            0,
            -1,
        )
        
        decisions = []
        for decision_id in decision_ids:
            decision = await self.get_decision(decision_id)
            if decision:
                decisions.append(decision)
        
        return decisions
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def _serialize_trace(self, trace: RequestTrace) -> dict[str, str]:
        """Serialize trace to Redis hash format."""
        return {
            "trace_id": trace.trace_id,
            "conversation_id": trace.conversation_id or "",
            "input_type": trace.input_type,
            "input_text": trace.input_text,
            "speaker_id": trace.speaker_id or "",
            "speaker_name": trace.speaker_name or "",
            "room": trace.room or "",
            "status": trace.status.value,
            "started_at": trace.started_at.isoformat() if trace.started_at else "",
            "completed_at": trace.completed_at.isoformat() if trace.completed_at else "",
            "total_duration_ms": str(trace.total_duration_ms or 0),
            "intent": trace.intent or "",
            "intent_confidence": str(trace.intent_confidence),
            "routed_to_agent": trace.routed_to_agent or "",
            "agent_used": trace.agent_used or "",
            "response_text": trace.response_text,
            "total_llm_calls": str(trace.total_llm_calls),
            "total_cost_usd": str(trace.total_cost_usd),
            "decision_ids": json.dumps(trace.decision_ids),
            "ha_actions": json.dumps(trace.ha_actions),
            "marked_as_wrong": "1" if trace.marked_as_wrong else "0",
            "correction_id": trace.correction_id or "",
            "error": trace.error or "",
        }
    
    def _deserialize_trace(self, data: dict[bytes, bytes]) -> RequestTrace:
        """Deserialize trace from Redis hash format."""
        # Convert bytes to strings
        data = {k.decode(): v.decode() for k, v in data.items()}
        
        return RequestTrace(
            trace_id=data["trace_id"],
            conversation_id=data.get("conversation_id") or None,
            input_type=data.get("input_type", "text"),
            input_text=data.get("input_text", ""),
            speaker_id=data.get("speaker_id") or None,
            speaker_name=data.get("speaker_name") or None,
            room=data.get("room") or None,
            status=TraceStatus(data.get("status", "completed")),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            total_duration_ms=float(data.get("total_duration_ms", 0)) or None,
            intent=data.get("intent") or None,
            intent_confidence=float(data.get("intent_confidence", 0)),
            routed_to_agent=data.get("routed_to_agent") or None,
            agent_used=data.get("agent_used") or None,
            response_text=data.get("response_text", ""),
            total_llm_calls=int(data.get("total_llm_calls", 0)),
            total_cost_usd=float(data.get("total_cost_usd", 0)),
            decision_ids=json.loads(data.get("decision_ids", "[]")),
            ha_actions=json.loads(data.get("ha_actions", "[]")),
            marked_as_wrong=data.get("marked_as_wrong") == "1",
            correction_id=data.get("correction_id") or None,
            error=data.get("error") or None,
        )
    
    def _serialize_decision(self, decision: DecisionRecord) -> dict[str, str]:
        """Serialize decision to Redis hash format."""
        return {
            "decision_id": decision.decision_id,
            "trace_id": decision.trace_id or "",
            "parent_decision_id": decision.parent_decision_id or "",
            "decision_type": decision.decision_type.value,
            "decision_name": decision.decision_name,
            "component": decision.component,
            "started_at": decision.started_at.isoformat(),
            "completed_at": decision.completed_at.isoformat() if decision.completed_at else "",
            "duration_ms": str(decision.duration_ms or 0),
            "inputs": json.dumps(self._serialize_inputs(decision.inputs)),
            "logic": json.dumps(self._serialize_logic(decision.logic)),
            "result": json.dumps(self._serialize_result(decision.result)),
            "child_decisions": json.dumps(decision.child_decisions),
            "error": decision.error or "",
            "error_type": decision.error_type or "",
        }
    
    def _serialize_inputs(self, inputs: Any) -> dict:
        """Serialize decision inputs."""
        if not inputs:
            return {}
        return {
            "primary": str(inputs.primary) if inputs.primary else None,
            "context": inputs.context,
        }
    
    def _serialize_logic(self, logic: Any) -> dict:
        """Serialize decision logic."""
        if not logic:
            return {}
        return {
            "logic_type": logic.logic_type,
            "logic_source": logic.logic_source,
            "logic_content": logic.logic_content if isinstance(logic.logic_content, (str, dict, list)) else str(logic.logic_content),
            "is_editable": logic.is_editable,
        }
    
    def _serialize_result(self, result: Any) -> dict:
        """Serialize decision result."""
        if not result:
            return {}
        return {
            "outcome": result.outcome.value,
            "value": str(result.value) if result.value else None,
            "confidence": result.confidence,
            "alternatives": result.alternatives,
            "explanation": result.explanation,
        }
    
    def _deserialize_decision(self, data: dict[bytes, bytes]) -> DecisionRecord:
        """Deserialize decision from Redis hash format."""
        # Convert bytes to strings
        data = {k.decode(): v.decode() for k, v in data.items()}
        
        from barnabeenet.core.decision_registry import (
            DecisionType, DecisionOutcome, DecisionInput, DecisionLogic, DecisionResult
        )
        
        inputs_data = json.loads(data.get("inputs", "{}"))
        logic_data = json.loads(data.get("logic", "{}"))
        result_data = json.loads(data.get("result", "{}"))
        
        return DecisionRecord(
            decision_id=data["decision_id"],
            trace_id=data.get("trace_id") or None,
            parent_decision_id=data.get("parent_decision_id") or None,
            decision_type=DecisionType(data.get("decision_type", "pattern_match")),
            decision_name=data.get("decision_name", ""),
            component=data.get("component", ""),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            duration_ms=float(data.get("duration_ms", 0)) or None,
            inputs=DecisionInput(
                primary=inputs_data.get("primary"),
                context=inputs_data.get("context", {}),
            ) if inputs_data else None,
            logic=DecisionLogic(
                logic_type=logic_data.get("logic_type", "unknown"),
                logic_source=logic_data.get("logic_source", ""),
                logic_content=logic_data.get("logic_content"),
                is_editable=logic_data.get("is_editable", False),
            ) if logic_data else None,
            result=DecisionResult(
                outcome=DecisionOutcome(result_data.get("outcome", "skipped")),
                value=result_data.get("value"),
                confidence=result_data.get("confidence", 0),
                alternatives=result_data.get("alternatives", []),
                explanation=result_data.get("explanation"),
            ) if result_data else None,
            child_decisions=json.loads(data.get("child_decisions", "[]")),
            error=data.get("error") or None,
            error_type=data.get("error_type") or None,
        )
```

---

## 5. Dashboard UI Specification

### 5.1 Main Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🐝 BarnabeeNet Pipeline Manager                              [Settings ⚙️] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Request List ───────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  [🔍 Search...] [Filter ▼] [Time Range ▼] [🔴 Show Wrong Only □]     │   │
│  │                                                                      │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │ ● 14:32:07 │ "turn off the office light"        │ ✅ │ 135ms  │ │   │
│  │  │   Thom • Office • action → light.turn_off        │    │        │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │ ● 14:31:45 │ "what's the weather"               │ ✅ │ 1.2s   │ │   │
│  │  │   Thom • Kitchen • interaction → response        │    │        │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │ ○ 14:30:22 │ "turn on the living room lamp"     │ 🔴 │ 89ms   │ │   │
│  │  │   Thom • Living Room • action → WRONG ENTITY     │    │ [FIX]  │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │ ● 14:28:15 │ "what time is it"                  │ ✅ │ 4ms    │ │   │
│  │  │   Penelope • Kitchen • instant → time            │    │        │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                      │   │
│  │  [Load More ↓]                                                       │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════│
│                                                                              │
│                         ↓ SELECT A REQUEST ABOVE ↓                          │
│                     to view detailed pipeline timeline                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Selected Request: Full Timeline View

When a request is selected from the list, the bottom section expands to show the complete timeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📋 Request: tr_7f8a3b2c                                    [Mark as Wrong] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Summary Bar ────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  INPUT: "turn off the office light"                                  │   │
│  │  SPEAKER: Thom (from HA context) • ROOM: Office                     │   │
│  │  RESULT: ✅ light.office_light turned off                           │   │
│  │                                                                      │   │
│  │  ⏱️ 135ms total │ 🧠 1 LLM call │ 💰 $0.00001 │ 📊 12 decisions       │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Waterfall Timeline ─────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  0ms              50ms             100ms            135ms            │   │
│  │  │                 │                 │                │              │   │
│  │  ├─ STT ──────────┤                                   │  (skipped)   │   │
│  │  │                ├─ Speaker ID ─┤                    │  (8ms)       │   │
│  │  │                │              ├─ Meta Agent ──────┤│  (15ms)      │   │
│  │  │                │              │                   ├┤─ Action ────┤  (34ms)
│  │  │                │              │                   ││            ├┤ TTS   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Decision Tree ──────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  [▼ Expand All] [▲ Collapse All] [View: Tree │ List │ JSON]          │   │
│  │                                                                      │   │
│  │  📥 INPUT PROCESSING                                                 │   │
│  │  ├── 🎤 stt.transcribe (skipped - text input)                       │   │
│  │  └── 👤 speaker.identify                                     8ms    │   │
│  │      ├── Input: device_id="dashboard"                               │   │
│  │      ├── Logic: HA user lookup → family profile fallback            │   │
│  │      └── Result: ✅ Thom (from HA user session)                     │   │
│  │                                                                      │   │
│  │  🧭 META AGENT                                               15ms   │   │
│  │  ├── [▼] 🚨 meta.check_emergency_patterns                   0.2ms   │   │
│  │  │       ├── Input: "turn off the office light"                     │   │
│  │  │       ├── Logic: 4 patterns checked [View Patterns]              │   │
│  │  │       │   ├── .*(fire|smoke|burning).*  ❌                       │   │
│  │  │       │   ├── .*(help|emergency|911).*  ❌                       │   │
│  │  │       │   ├── .*(intruder|break.?in).*  ❌                       │   │
│  │  │       │   └── .*(fall|fallen|can't get up).*  ❌                 │   │
│  │  │       └── Result: ❌ No match                                    │   │
│  │  │                                                                  │   │
│  │  ├── [▼] ⚡ meta.check_instant_patterns                     0.3ms   │   │
│  │  │       ├── Input: "turn off the office light"                     │   │
│  │  │       ├── Logic: 7 patterns checked [View Patterns]              │   │
│  │  │       │   ├── ^(what's|what is) the time.*  ❌                   │   │
│  │  │       │   ├── ^(what's|what is) (today's )?date.*  ❌            │   │
│  │  │       │   ├── ^(hello|hey|hi).*  ❌                              │   │
│  │  │       │   ├── ^good (morning|afternoon|evening).*  ❌            │   │
│  │  │       │   ├── ^\d+\s*[\+\-\*\/]\s*\d+.*  ❌                      │   │
│  │  │       │   ├── ^(how are you|you okay).*  ❌                      │   │
│  │  │       │   └── ^thank(s| you).*  ❌                               │   │
│  │  │       └── Result: ❌ No match                                    │   │
│  │  │                                                                  │   │
│  │  ├── [▼] 🎯 meta.check_action_patterns                      0.4ms   │   │
│  │  │       ├── Input: "turn off the office light"                     │   │
│  │  │       ├── Logic: 8 patterns checked [View Patterns] [✏️ Edit]    │   │
│  │  │       │   ├── ^(turn|trun|tunr|switch|swtich) (on|off|of) .*  ✅│   │
│  │  │       │   │   └── Match groups: ["turn", "off", "the office light"]
│  │  │       │   │                                                      │   │
│  │  │       │   ├── ^(set|change) .* to .*$  (not checked - prior match)
│  │  │       │   └── ... 6 more patterns (not checked)                  │   │
│  │  │       │                                                          │   │
│  │  │       ├── Result: ✅ MATCH                                       │   │
│  │  │       │   ├── Pattern: "switch_control"                          │   │
│  │  │       │   ├── Sub-category: "switch"                             │   │
│  │  │       │   └── Confidence: 0.95                                   │   │
│  │  │       │                                                          │   │
│  │  │       └── [🔧 Test Different Input] [✏️ Edit This Pattern]       │   │
│  │  │                                                                  │   │
│  │  ├── [▶] 🎭 meta.evaluate_context                           2ms     │   │
│  │  │       └── Result: tone=neutral, urgency=low, empathy=false       │   │
│  │  │                                                                  │   │
│  │  └── [▶] 🚦 meta.route                                      0.5ms   │   │
│  │          ├── Logic: Intent → Agent mapping [View Rules] [✏️ Edit]   │   │
│  │          │   └── ACTION → action_agent (default rule)               │   │
│  │          └── Result: ✅ Route to action_agent, priority=7           │   │
│  │                                                                      │   │
│  │  🎯 ACTION AGENT                                             34ms   │   │
│  │  ├── [▼] 🔍 action.resolve_entities                         5ms     │   │
│  │  │       ├── Input: "the office light"                              │   │
│  │  │       ├── Context: room=Office, speaker=Thom                     │   │
│  │  │       ├── Logic: SmartEntityResolver [View Config] [✏️ Edit]     │   │
│  │  │       │   ├── Step 1: Extract entity reference "office light"    │   │
│  │  │       │   ├── Step 2: Search HA entities                         │   │
│  │  │       │   │   ├── light.office_light (score: 0.92)              │   │
│  │  │       │   │   ├── light.office_desk (score: 0.67)               │   │
│  │  │       │   │   └── light.office_fan (score: 0.54)                │   │
│  │  │       │   └── Step 3: Apply room context boost (+0.1)            │   │
│  │  │       │                                                          │   │
│  │  │       ├── Result: ✅ light.office_light (confidence: 0.92)       │   │
│  │  │       │   └── Alternatives: [light.office_desk, light.office_fan]│   │
│  │  │       │                                                          │   │
│  │  │       └── [✏️ Add Entity Alias] [✏️ Edit Resolution Rules]       │   │
│  │  │                                                                  │   │
│  │  ├── [▼] 🔧 action.determine_service                       12ms     │   │
│  │  │       ├── Input: entity=light.office_light, action_word="off"    │   │
│  │  │       ├── Logic: LLM call (deepseek-v3) [View Prompt] [✏️ Edit]  │   │
│  │  │       │   ┌────────────────────────────────────────────────────┐│   │
│  │  │       │   │ SYSTEM PROMPT (147 tokens)              [Expand ▼] ││   │
│  │  │       │   │ You are processing a home control command...       ││   │
│  │  │       │   │                                                    ││   │
│  │  │       │   │ USER MESSAGE (23 tokens)                           ││   │
│  │  │       │   │ Turn off light.office_light                        ││   │
│  │  │       │   │                                                    ││   │
│  │  │       │   │ RESPONSE (18 tokens)                               ││   │
│  │  │       │   │ {"service": "light.turn_off", "entity_id": "..."}  ││   │
│  │  │       │   └────────────────────────────────────────────────────┘│   │
│  │  │       │                                                          │   │
│  │  │       ├── Tokens: 147 in / 18 out | Cost: $0.00001              │   │
│  │  │       └── Result: ✅ service=light.turn_off                     │   │
│  │  │                                                                  │   │
│  │  ├── [▼] 📡 action.call_ha                                 15ms     │   │
│  │  │       ├── Service: light.turn_off                                │   │
│  │  │       ├── Entity: light.office_light                             │   │
│  │  │       ├── Service Data: {}                                       │   │
│  │  │       │                                                          │   │
│  │  │       ├── HA Response: SUCCESS                                   │   │
│  │  │       │   ├── Before state: on, brightness=255                  │   │
│  │  │       │   └── After state: off                                   │   │
│  │  │       │                                                          │   │
│  │  │       └── [View Entity History] [View HA Logs]                   │   │
│  │  │                                                                  │   │
│  │  └── [▶] 💬 action.generate_response                       2ms      │   │
│  │          └── Result: "Done, I've turned off the office light."      │   │
│  │                                                                      │   │
│  │  🔊 OUTPUT                                                  78ms    │   │
│  │  └── [▶] tts.synthesize                                    78ms     │   │
│  │          ├── Text: "Done, I've turned off the office light."        │   │
│  │          ├── Voice: bm_fable [Change ▼]                             │   │
│  │          ├── Duration: 1.2s                                         │   │
│  │          └── [▶ Play Audio]                                         │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Actions ────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  [🔴 Mark as Wrong]  [🔁 Re-run Request]  [📋 Copy Trace JSON]       │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Pipeline Timeline View

### 6.1 Decision Node Component

Each decision in the timeline is an expandable component:

```typescript
// components/DecisionNode.tsx

interface DecisionNodeProps {
  decision: DecisionRecord;
  depth: number;
  isExpanded: boolean;
  onToggle: () => void;
  onEditLogic: (logicId: string) => void;
  onTestInput: (decisionName: string, testInput: string) => void;
}

const DecisionNode: React.FC<DecisionNodeProps> = ({
  decision,
  depth,
  isExpanded,
  onToggle,
  onEditLogic,
  onTestInput,
}) => {
  const icons: Record<string, string> = {
    pattern_match: "🔍",
    llm_call: "🤖",
    entity_resolution: "🏠",
    routing: "🚦",
    service_call: "📡",
    override_check: "⚙️",
    threshold_check: "📊",
    model_selection: "🎛️",
    prompt_render: "📝",
    response_generation: "💬",
  };

  const outcomeColors: Record<string, string> = {
    match: "text-green-500",
    selected: "text-green-500",
    no_match: "text-gray-400",
    rejected: "text-gray-400",
    skipped: "text-gray-300",
    error: "text-red-500",
    overridden: "text-yellow-500",
  };

  return (
    <div className={`decision-node depth-${depth}`}>
      {/* Header - Always visible */}
      <div className="decision-header" onClick={onToggle}>
        <span className="expand-icon">{isExpanded ? "▼" : "▶"}</span>
        <span className="decision-icon">{icons[decision.decision_type]}</span>
        <span className="decision-name">{decision.decision_name}</span>
        <span className={`decision-outcome ${outcomeColors[decision.result?.outcome]}`}>
          {decision.result?.outcome === "match" ? "✅" : 
           decision.result?.outcome === "error" ? "❌" : "○"}
        </span>
        <span className="decision-duration">{decision.duration_ms?.toFixed(1)}ms</span>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="decision-details">
          {/* Inputs Section */}
          <div className="detail-section">
            <h4>Input</h4>
            <pre>{JSON.stringify(decision.inputs, null, 2)}</pre>
          </div>

          {/* Logic Section - with edit button if editable */}
          <div className="detail-section">
            <h4>
              Logic
              {decision.logic?.is_editable && (
                <button 
                  className="edit-btn"
                  onClick={() => onEditLogic(decision.logic.logic_source)}
                >
                  ✏️ Edit
                </button>
              )}
            </h4>
            <div className="logic-source">
              Source: <code>{decision.logic?.logic_source}</code>
            </div>
            {decision.logic?.logic_content && (
              <pre>{formatLogicContent(decision.logic.logic_content)}</pre>
            )}
          </div>

          {/* Result Section */}
          <div className="detail-section">
            <h4>Result</h4>
            <div className="result-outcome">
              Outcome: <strong>{decision.result?.outcome}</strong>
              {decision.result?.confidence && (
                <span> (confidence: {(decision.result.confidence * 100).toFixed(0)}%)</span>
              )}
            </div>
            {decision.result?.value && (
              <pre>{JSON.stringify(decision.result.value, null, 2)}</pre>
            )}
            {decision.result?.alternatives?.length > 0 && (
              <div className="alternatives">
                <h5>Alternatives Considered:</h5>
                <ul>
                  {decision.result.alternatives.map((alt, i) => (
                    <li key={i}>{JSON.stringify(alt)}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Test Input Section */}
          <div className="detail-section">
            <button
              className="test-btn"
              onClick={() => onTestInput(decision.decision_name, "")}
            >
              🔧 Test with Different Input
            </button>
          </div>
        </div>
      )}

      {/* Child Decisions */}
      {decision.child_decisions?.length > 0 && isExpanded && (
        <div className="child-decisions">
          {/* Render children recursively */}
        </div>
      )}
    </div>
  );
};
```

### 6.2 Pattern Display Component

For pattern match decisions, show each pattern that was checked:

```typescript
// components/PatternList.tsx

interface PatternListProps {
  patterns: PatternCheckRecord[];
  matchedIndex: number | null;
  onEditPattern: (patternId: string) => void;
}

const PatternList: React.FC<PatternListProps> = ({
  patterns,
  matchedIndex,
  onEditPattern,
}) => {
  return (
    <div className="pattern-list">
      {patterns.map((pattern, index) => (
        <div 
          key={index}
          className={`pattern-item ${
            pattern.matched ? "matched" : 
            index > matchedIndex ? "not-checked" : "not-matched"
          }`}
        >
          <span className="pattern-status">
            {pattern.matched ? "✅" : 
             index > matchedIndex ? "⏭️" : "❌"}
          </span>
          <code className="pattern-regex">{pattern.pattern}</code>
          {pattern.matched && pattern.match_groups && (
            <span className="match-groups">
              Groups: {JSON.stringify(pattern.match_groups)}
            </span>
          )}
          <button 
            className="edit-pattern-btn"
            onClick={() => onEditPattern(`patterns.${pattern.group}.${index}`)}
          >
            ✏️
          </button>
        </div>
      ))}
    </div>
  );
};
```

---

## 7. AI Correction Assistant

### 7.1 Correction Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🔴 Fix This Request                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Step 1: What Went Wrong? ───────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  Request: "turn on the living room lamp"                             │   │
│  │  What happened: Turned on ALL living room lights                     │   │
│  │                                                                      │   │
│  │  What should have happened?                                          │   │
│  │  [Only turn on light.living_room_lamp                              ] │   │
│  │                                                                      │   │
│  │  Issue type:                                                         │   │
│  │  (●) Wrong entity selected                                           │   │
│  │  ( ) Wrong action performed                                          │   │
│  │  ( ) Should have asked for clarification                             │   │
│  │  ( ) Wrong agent routing                                             │   │
│  │  ( ) Response tone/content issue                                     │   │
│  │  ( ) Other                                                           │   │
│  │                                                                      │   │
│  │                                         [Analyze with AI →]          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 AI Analysis Service

```python
# services/ai_correction.py
"""
AI Correction Assistant - Diagnoses issues and proposes fixes.

This service has FULL ACCESS to:
- The complete trace with all decisions
- The logic configurations that were used
- The code that implements each decision type
- Historical patterns of similar issues
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from barnabeenet.services.llm.openrouter import OpenRouterClient
from barnabeenet.core.decision_registry import DecisionRecord
from barnabeenet.core.logic_registry import LogicRegistry, LogicDefinition
from barnabeenet.models.traces import RequestTrace

logger = structlog.get_logger()


@dataclass
class CorrectionSuggestion:
    """A suggested fix for an issue."""
    
    suggestion_id: str
    suggestion_type: str  # "pattern_add", "pattern_modify", "prompt_edit", etc.
    priority: int  # 1 = highest priority suggestion
    
    title: str
    description: str
    impact_level: str  # "low", "medium", "high"
    
    # What to change
    target_logic_id: str
    current_value: Any
    proposed_value: Any
    
    # Diff view
    diff_before: str
    diff_after: str
    
    # Testing
    test_inputs: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    
    # Confidence
    ai_confidence: float = 0.0
    ai_reasoning: str = ""


@dataclass
class CorrectionAnalysis:
    """Complete analysis of why a request failed and how to fix it."""
    
    analysis_id: str
    trace_id: str
    timestamp: datetime
    
    # User input
    expected_result: str
    issue_type: str
    
    # AI diagnosis
    root_cause: str
    root_cause_decision_id: str  # Which decision caused the issue
    root_cause_logic_id: str  # Which logic was at fault
    
    # Similar historical issues
    similar_traces: list[str] = field(default_factory=list)
    similar_corrections: list[str] = field(default_factory=list)
    
    # Suggestions (ordered by priority)
    suggestions: list[CorrectionSuggestion] = field(default_factory=list)
    
    # Selected fix
    selected_suggestion_id: str | None = None
    applied_at: datetime | None = None
    applied_by: str | None = None
    
    # Verification
    verification_status: str = "pending"  # "pending", "verified", "failed", "reverted"
    verification_trace_ids: list[str] = field(default_factory=list)


class AICorrectionAssistant:
    """
    AI-powered assistant for diagnosing and fixing pipeline issues.
    
    Key capabilities:
    1. Analyze a trace to identify the root cause of an issue
    2. Search for similar historical issues
    3. Generate fix suggestions with full context
    4. Test proposed fixes against historical data
    5. Apply fixes with hot-reload
    """
    
    ANALYSIS_PROMPT = """You are an expert at debugging BarnabeeNet's pipeline.

## Your Task
Analyze this request trace and determine why it produced the wrong result.

## Request Information
- Input: "{input_text}"
- Expected result: "{expected_result}"  
- Actual result: "{actual_result}"
- Issue type reported by user: "{issue_type}"

## Complete Decision Trail
{decision_trail}

## Logic Configurations Used
{logic_configs}

## Similar Historical Issues
{similar_issues}

## Analysis Required
1. Identify the ROOT CAUSE decision - which specific decision in the trail led to the wrong outcome?
2. Identify the LOGIC at fault - what pattern/prompt/config caused this?
3. Explain WHY this logic failed for this input
4. Suggest 2-3 SPECIFIC fixes, ordered by:
   - Priority (how likely to fix the issue)
   - Impact level (low = only affects this case, high = affects many cases)

## Response Format
Respond with JSON:
```json
{
  "root_cause": "Brief description of what went wrong",
  "root_cause_decision_id": "decision_id from trail",
  "root_cause_logic_id": "logic_id that needs fixing",
  "why_it_failed": "Detailed explanation",
  "suggestions": [
    {
      "suggestion_type": "pattern_modify|prompt_edit|entity_alias|override_add|routing_change",
      "title": "Brief title",
      "description": "What this fix does",
      "impact_level": "low|medium|high",
      "target_logic_id": "logic_id to modify",
      "proposed_change": "The new value/content",
      "reasoning": "Why this fix will work",
      "test_cases": ["input 1", "input 2"],
      "confidence": 0.0-1.0
    }
  ]
}
```"""

    def __init__(
        self,
        llm_client: OpenRouterClient,
        logic_registry: LogicRegistry,
        decision_logger: Any,  # DecisionLogger
    ):
        self.llm = llm_client
        self.logic_registry = logic_registry
        self.decision_logger = decision_logger
    
    async def analyze_trace(
        self,
        trace_id: str,
        expected_result: str,
        issue_type: str,
    ) -> CorrectionAnalysis:
        """Analyze a trace and generate fix suggestions."""
        
        # 1. Get the full trace
        trace = await self.decision_logger.get_trace(trace_id)
        if not trace:
            raise ValueError(f"Trace not found: {trace_id}")
        
        # 2. Get all decisions for the trace
        decisions = await self.decision_logger.get_trace_decisions(trace_id)
        
        # 3. Get the logic configurations that were used
        logic_configs = await self._get_logic_configs_for_decisions(decisions)
        
        # 4. Find similar historical issues
        similar = await self._find_similar_issues(trace.input_text, issue_type)
        
        # 5. Build the decision trail for the prompt
        decision_trail = self._format_decision_trail(decisions)
        
        # 6. Call AI for analysis
        prompt = self.ANALYSIS_PROMPT.format(
            input_text=trace.input_text,
            expected_result=expected_result,
            actual_result=trace.response_text,
            issue_type=issue_type,
            decision_trail=decision_trail,
            logic_configs=json.dumps(logic_configs, indent=2),
            similar_issues=self._format_similar_issues(similar),
        )
        
        response = await self.llm.complete(
            model="anthropic/claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        
        # 7. Parse AI response
        analysis_data = json.loads(response.content)
        
        # 8. Build suggestions with full diff information
        suggestions = []
        for i, sugg_data in enumerate(analysis_data.get("suggestions", [])):
            # Get current logic value
            logic = await self.logic_registry.get_logic(sugg_data["target_logic_id"])
            current_value = logic.content if logic else None
            
            suggestions.append(CorrectionSuggestion(
                suggestion_id=f"sugg_{trace_id}_{i}",
                suggestion_type=sugg_data["suggestion_type"],
                priority=i + 1,
                title=sugg_data["title"],
                description=sugg_data["description"],
                impact_level=sugg_data["impact_level"],
                target_logic_id=sugg_data["target_logic_id"],
                current_value=current_value,
                proposed_value=sugg_data["proposed_change"],
                diff_before=self._format_for_diff(current_value),
                diff_after=self._format_for_diff(sugg_data["proposed_change"]),
                test_inputs=sugg_data.get("test_cases", [trace.input_text]),
                ai_confidence=sugg_data.get("confidence", 0.7),
                ai_reasoning=sugg_data.get("reasoning", ""),
            ))
        
        return CorrectionAnalysis(
            analysis_id=f"analysis_{trace_id}_{datetime.now().timestamp()}",
            trace_id=trace_id,
            timestamp=datetime.now(),
            expected_result=expected_result,
            issue_type=issue_type,
            root_cause=analysis_data["root_cause"],
            root_cause_decision_id=analysis_data["root_cause_decision_id"],
            root_cause_logic_id=analysis_data["root_cause_logic_id"],
            similar_traces=[s["trace_id"] for s in similar],
            suggestions=suggestions,
        )
    
    async def test_suggestion(
        self,
        suggestion: CorrectionSuggestion,
        historical_trace_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Test a suggestion against historical data without applying it."""
        
        results = {
            "suggestion_id": suggestion.suggestion_id,
            "test_results": [],
            "would_fix_original": False,
            "regression_count": 0,
            "improvement_count": 0,
        }
        
        # Get traces to test against
        if historical_trace_ids:
            traces = [
                await self.decision_logger.get_trace(tid) 
                for tid in historical_trace_ids
            ]
        else:
            # Get recent similar traces
            traces = await self._get_similar_recent_traces(
                suggestion.target_logic_id,
                limit=20,
            )
        
        # Simulate the change for each trace
        for trace in traces:
            if not trace:
                continue
            
            # Run the pipeline with the proposed change
            simulated_result = await self._simulate_with_change(
                trace=trace,
                logic_id=suggestion.target_logic_id,
                new_value=suggestion.proposed_value,
            )
            
            # Compare to actual result
            test_result = {
                "trace_id": trace.trace_id,
                "input": trace.input_text,
                "original_result": trace.response_text,
                "simulated_result": simulated_result,
                "was_wrong": trace.marked_as_wrong,
            }
            
            if trace.marked_as_wrong:
                # This was a known issue - did we fix it?
                if simulated_result != trace.response_text:
                    test_result["status"] = "fixed"
                    results["improvement_count"] += 1
                else:
                    test_result["status"] = "still_wrong"
            else:
                # This was working - did we break it?
                if simulated_result != trace.response_text:
                    test_result["status"] = "regression"
                    results["regression_count"] += 1
                else:
                    test_result["status"] = "unchanged"
            
            results["test_results"].append(test_result)
        
        return results
    
    async def apply_suggestion(
        self,
        analysis_id: str,
        suggestion_id: str,
        user: str,
    ) -> CorrectionAnalysis:
        """Apply a suggested fix."""
        
        # Get the analysis and suggestion
        analysis = await self._get_analysis(analysis_id)
        suggestion = next(
            (s for s in analysis.suggestions if s.suggestion_id == suggestion_id),
            None,
        )
        
        if not suggestion:
            raise ValueError(f"Suggestion not found: {suggestion_id}")
        
        # Apply the change via LogicRegistry
        await self.logic_registry.update_logic(
            logic_id=suggestion.target_logic_id,
            new_content=suggestion.proposed_value,
            reason=f"AI correction: {suggestion.title}",
            user=user,
        )
        
        # Update analysis
        analysis.selected_suggestion_id = suggestion_id
        analysis.applied_at = datetime.now()
        analysis.applied_by = user
        
        # Mark the original trace
        trace = await self.decision_logger.get_trace(analysis.trace_id)
        trace.correction_id = analysis.analysis_id
        await self.decision_logger.update_trace(trace)
        
        return analysis
    
    async def _get_logic_configs_for_decisions(
        self,
        decisions: list[DecisionRecord],
    ) -> dict[str, Any]:
        """Get all logic configurations used in the decisions."""
        configs = {}
        for decision in decisions:
            if decision.logic and decision.logic.logic_source:
                logic_id = decision.logic.logic_source
                if logic_id not in configs:
                    logic = await self.logic_registry.get_logic(logic_id)
                    if logic:
                        configs[logic_id] = {
                            "type": logic.logic_type,
                            "content": logic.content,
                            "editable": logic.editable,
                        }
        return configs
    
    def _format_decision_trail(self, decisions: list[DecisionRecord]) -> str:
        """Format decisions for the analysis prompt."""
        lines = []
        for i, d in enumerate(decisions):
            lines.append(f"""
Decision {i+1}: {d.decision_name}
  Type: {d.decision_type.value}
  Duration: {d.duration_ms:.1f}ms
  Input: {json.dumps(d.inputs.primary if d.inputs else None)}
  Logic: {d.logic.logic_source if d.logic else 'N/A'}
  Outcome: {d.result.outcome.value if d.result else 'N/A'}
  Result: {d.result.value if d.result else 'N/A'}
  Confidence: {d.result.confidence if d.result else 0}
""")
        return "\n".join(lines)
    
    async def _find_similar_issues(
        self,
        input_text: str,
        issue_type: str,
    ) -> list[dict[str, Any]]:
        """Find similar historical issues."""
        # This would use embedding similarity search
        # For now, return empty
        return []
    
    def _format_similar_issues(self, similar: list[dict]) -> str:
        """Format similar issues for the prompt."""
        if not similar:
            return "No similar historical issues found."
        
        lines = []
        for s in similar[:5]:
            lines.append(f"- Input: '{s['input']}' → Fixed by: {s['fix_type']}")
        return "\n".join(lines)
    
    def _format_for_diff(self, value: Any) -> str:
        """Format a value for diff display."""
        if isinstance(value, str):
            return value
        return json.dumps(value, indent=2)
    
    async def _simulate_with_change(
        self,
        trace: RequestTrace,
        logic_id: str,
        new_value: Any,
    ) -> str:
        """Simulate running a trace with a proposed change."""
        # This would re-run the pipeline with the change
        # For now, return placeholder
        return "simulated_result"
```

### 7.3 Correction UI Component

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🤖 AI Analysis Complete                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Root Cause ─────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  The SmartEntityResolver matched "living room lamp" to a LIGHT      │   │
│  │  GROUP instead of the individual lamp entity.                        │   │
│  │                                                                      │   │
│  │  Problem Decision: action.resolve_entities                           │   │
│  │  Problem Logic: config/entity_aliases.yaml                          │   │
│  │                                                                      │   │
│  │  Why: The entity "light.living_room_lamp" has friendly_name         │   │
│  │  "Living Room Lights" (plural), which caused group matching.         │   │
│  │                                                                      │   │
│  │  Similar Issues: 3 found in last 7 days [View]                       │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Suggested Fixes ────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ 🥇 Suggestion 1: Add entity alias (RECOMMENDED)               │   │   │
│  │  │    Confidence: 92% | Impact: Low (only affects "lamp" queries)│   │   │
│  │  │                                                               │   │   │
│  │  │    Add alias "lamp" to light.living_room_lamp so it gets      │   │   │
│  │  │    prioritized when user says "lamp" specifically.            │   │   │
│  │  │                                                               │   │   │
│  │  │    Diff:                                                      │   │   │
│  │  │    ┌──────────────────────────────────────────────────────┐  │   │   │
│  │  │    │ config/entity_aliases.yaml                           │  │   │   │
│  │  │    │                                                      │  │   │   │
│  │  │    │ + light.living_room_lamp:                            │  │   │   │
│  │  │    │ +   aliases:                                         │  │   │   │
│  │  │    │ +     - "lamp"                                       │  │   │   │
│  │  │    │ +     - "living room lamp"                           │  │   │   │
│  │  │    │ +   priority: high                                   │  │   │   │
│  │  │    └──────────────────────────────────────────────────────┘  │   │   │
│  │  │                                                               │   │   │
│  │  │    [Test This Fix] [Apply This Fix]                          │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ 🥈 Suggestion 2: Modify entity resolution prompt              │   │   │
│  │  │    Confidence: 78% | Impact: Medium (affects all resolution) │   │   │
│  │  │                                                               │   │   │
│  │  │    Update Action Agent prompt to prefer singular entities     │   │   │
│  │  │    when user uses singular nouns ("lamp" vs "lights").        │   │   │
│  │  │                                                               │   │   │
│  │  │    [View Full Diff] [Test This Fix] [Apply This Fix]          │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │ 🥉 Suggestion 3: Add override rule                            │   │   │
│  │  │    Confidence: 65% | Impact: Low (specific phrase only)      │   │   │
│  │  │                                                               │   │   │
│  │  │    Add override: "living room lamp" → light.living_room_lamp  │   │   │
│  │  │                                                               │   │   │
│  │  │    [View Full Diff] [Test This Fix] [Apply This Fix]          │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Test Results ───────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  Testing Suggestion 1 against 20 historical requests...              │   │
│  │                                                                      │   │
│  │  ✅ Would fix original issue                                         │   │
│  │  ✅ 3 similar issues would be fixed                                  │   │
│  │  ✅ 0 regressions detected                                           │   │
│  │  ○ 16 requests unchanged (expected)                                  │   │
│  │                                                                      │   │
│  │  [Apply Suggestion 1]                                                │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Editable Logic System

### 8.1 Configuration File Structure

```yaml
# config/patterns.yaml
# All pattern groups - fully editable via dashboard

pattern_groups:
  emergency:
    description: "Safety-critical patterns - checked first"
    priority: 1
    patterns:
      - name: fire_detection
        pattern: ".*(fire|smoke|burning|flames).*"
        sub_category: fire
        description: "Detect fire-related emergencies"
        
      - name: help_request
        pattern: ".*(help|emergency|911|ambulance).*"
        sub_category: emergency
        description: "General emergency requests"

  instant:
    description: "Simple queries - no LLM needed"
    priority: 2
    patterns:
      - name: time_query
        pattern: "^(what('s| is) the )?(current )?time(\\?)?$"
        sub_category: time
        response_template: "It's {current_time}"
        
      - name: date_query
        pattern: "^(what('s| is) )?(today'?s? )?date(\\?)?$"
        sub_category: date
        response_template: "Today is {current_date}"

  action:
    description: "Device control patterns"
    priority: 3
    patterns:
      - name: switch_control
        pattern: "^(turn|trun|tunr|switch|swtich) (on|off|of) .*$"
        sub_category: switch
        description: "Turn devices on/off"
        typo_tolerance:
          - trun -> turn
          - tunr -> turn
          - swtich -> switch
          - of -> off
          
      - name: set_value
        pattern: "^(set|change) .* to .*$"
        sub_category: set
        description: "Set device values"
        
      - name: dim_lights
        pattern: "^(dim|brighten) .*$"
        sub_category: light
        description: "Adjust light brightness"
```

```yaml
# config/routing.yaml
# Agent routing rules - fully editable

defaults:
  unknown_intent: interaction
  low_confidence_threshold: 0.7
  llm_fallback_model: deepseek/deepseek-v3

rules:
  instant_to_instant:
    intent: instant
    target_agent: instant
    description: "Simple queries go to instant agent"
    
  action_to_action:
    intent: action
    target_agent: action
    description: "Device control goes to action agent"
    
  query_to_interaction:
    intent: query
    target_agent: interaction
    description: "Complex queries go to interaction agent"
    
  emergency_to_action:
    intent: emergency
    target_agent: action
    priority_boost: 3
    description: "Emergencies routed to action with high priority"
```

```yaml
# config/overrides.yaml
# Override rules - checked before normal routing

overrides:
  kids_bedtime:
    name: "Kids Bedtime Mode"
    description: "Restrict kids' access during bedtime"
    enabled: true
    
    conditions:
      - type: time_range
        start: "20:00"
        end: "21:00"
      - type: speaker_in
        values: [penelope, xander, zachary, viola]
      - type: room_in
        values: [bedroom.penelope, bedroom.xander, bedroom.zachary, bedroom.viola]
    
    actions:
      - type: block_intent
        intents: [action]
        domains: [media_player, light]  # Only block entertainment
        response: "It's bedtime! Ask mom or dad if you need something."
        
  quiet_hours:
    name: "Quiet Hours"
    description: "Reduce volume and limit proactive notifications at night"
    enabled: true
    
    conditions:
      - type: time_range
        start: "22:00"
        end: "07:00"
    
    actions:
      - type: modify_tts
        volume: 0.3
      - type: block_proactive
        except_categories: [emergency]
```

```yaml
# config/entity_aliases.yaml
# Entity aliases for better resolution

aliases:
  light.living_room_lamp:
    aliases:
      - lamp
      - living room lamp
      - the lamp
    priority: high
    
  light.office_light:
    aliases:
      - office light
      - desk light
    room_context: office
    
  media_player.living_room_tv:
    aliases:
      - tv
      - television
      - the tv
    room_context: living_room
```

### 8.2 Hot-Reload System

```python
# core/hot_reload.py
"""
Hot-reload system for configuration changes.

When logic is updated via the dashboard, this system:
1. Validates the new configuration
2. Persists it to disk
3. Notifies all workers to reload
4. Verifies the reload was successful
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

import redis.asyncio as redis
import yaml
import structlog

logger = structlog.get_logger()


class HotReloadManager:
    """Manages hot-reload of configuration across all workers."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        config_dir: Path,
    ):
        self.redis = redis_client
        self.config_dir = config_dir
        self._reload_handlers: dict[str, Callable] = {}
        self._subscriber_task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start listening for reload events."""
        self._subscriber_task = asyncio.create_task(self._subscribe_loop())
        logger.info("Hot-reload manager started")
    
    async def stop(self) -> None:
        """Stop the reload listener."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
    
    def register_handler(
        self,
        config_type: str,
        handler: Callable[[str, Any], None],
    ) -> None:
        """Register a handler for a config type reload."""
        self._reload_handlers[config_type] = handler
    
    async def trigger_reload(
        self,
        config_type: str,
        config_id: str,
        new_value: Any,
    ) -> None:
        """Trigger a reload across all workers."""
        await self.redis.publish(
            "barnabeenet:config_reload",
            json.dumps({
                "config_type": config_type,
                "config_id": config_id,
                "timestamp": datetime.now().isoformat(),
            }),
        )
        
        logger.info(
            "Reload triggered",
            config_type=config_type,
            config_id=config_id,
        )
    
    async def _subscribe_loop(self) -> None:
        """Subscribe to reload events."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("barnabeenet:config_reload")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self._handle_reload(data)
    
    async def _handle_reload(self, data: dict) -> None:
        """Handle a reload event."""
        config_type = data["config_type"]
        config_id = data["config_id"]
        
        handler = self._reload_handlers.get(config_type)
        if handler:
            # Reload from disk
            new_value = await self._load_config(config_type, config_id)
            handler(config_id, new_value)
            
            logger.info(
                "Config reloaded",
                config_type=config_type,
                config_id=config_id,
            )
    
    async def _load_config(
        self,
        config_type: str,
        config_id: str,
    ) -> Any:
        """Load a config value from disk."""
        config_files = {
            "patterns": "patterns.yaml",
            "routing": "routing.yaml",
            "overrides": "overrides.yaml",
            "models": "models.yaml",
            "entity_aliases": "entity_aliases.yaml",
        }
        
        file_name = config_files.get(config_type)
        if not file_name:
            return None
        
        file_path = self.config_dir / file_name
        with open(file_path) as f:
            config = yaml.safe_load(f)
        
        # Navigate to the specific config_id
        parts = config_id.split(".")
        value = config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                value = value[int(part)]
            else:
                return None
        
        return value
```

---

## 9. Data Models

### 9.1 Complete Schema

```python
# models/pipeline.py
"""
Complete data models for the Pipeline Management Dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ============================================================================
# ENUMS
# ============================================================================

class DecisionType(Enum):
    PATTERN_MATCH = "pattern_match"
    LLM_CALL = "llm_call"
    ENTITY_RESOLUTION = "entity_resolution"
    ROUTING = "routing"
    SERVICE_CALL = "service_call"
    OVERRIDE_CHECK = "override_check"
    THRESHOLD_CHECK = "threshold_check"
    MODEL_SELECTION = "model_selection"
    PROMPT_RENDER = "prompt_render"
    RESPONSE_GENERATION = "response_generation"


class DecisionOutcome(Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    SELECTED = "selected"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    ERROR = "error"
    OVERRIDDEN = "overridden"


class TraceStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CorrectionStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    SUGGESTIONS_READY = "suggestions_ready"
    APPLIED = "applied"
    VERIFIED = "verified"
    FAILED = "failed"
    REVERTED = "reverted"


class IssueType(Enum):
    WRONG_ENTITY = "wrong_entity"
    WRONG_ACTION = "wrong_action"
    WRONG_ROUTING = "wrong_routing"
    SHOULD_CLARIFY = "should_clarify"
    WRONG_RESPONSE = "wrong_response"
    TONE_ISSUE = "tone_issue"
    OTHER = "other"


# ============================================================================
# CORE MODELS
# ============================================================================

@dataclass
class PatternDefinition:
    """A single pattern in a pattern group."""
    name: str
    pattern: str
    sub_category: str
    description: str = ""
    response_template: str | None = None
    typo_tolerance: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    
    # Stats (populated at runtime)
    match_count_24h: int = 0
    false_positive_count_24h: int = 0


@dataclass
class PatternGroup:
    """A group of related patterns."""
    name: str
    description: str
    priority: int
    patterns: list[PatternDefinition] = field(default_factory=list)


@dataclass
class RoutingRule:
    """A rule for routing intents to agents."""
    name: str
    intent: str
    target_agent: str
    description: str = ""
    priority_boost: int = 0
    conditions: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = True


@dataclass
class OverrideRule:
    """An override rule that modifies normal behavior."""
    name: str
    description: str
    enabled: bool
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    
    # Stats
    trigger_count_24h: int = 0
    last_triggered: datetime | None = None


@dataclass
class EntityAlias:
    """Alias configuration for an entity."""
    entity_id: str
    aliases: list[str]
    priority: str = "normal"  # "low", "normal", "high"
    room_context: str | None = None


# ============================================================================
# TRACE MODELS
# ============================================================================

@dataclass
class PatternCheckRecord:
    """Record of a single pattern check."""
    pattern_name: str
    pattern: str
    group: str
    check_order: int
    matched: bool
    match_groups: list[str] | None = None
    check_time_ms: float = 0


@dataclass
class LLMCallRecord:
    """Record of an LLM call."""
    model: str
    provider: str
    temperature: float
    max_tokens: int
    
    system_prompt: str
    user_message: str
    response: str
    
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


@dataclass
class HAActionRecord:
    """Record of a Home Assistant action."""
    domain: str
    service: str
    entity_id: str
    service_data: dict[str, Any]
    
    result: str  # "success", "error", "timeout"
    error_message: str | None = None
    
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    
    latency_ms: float = 0


@dataclass
class DecisionInput:
    """Inputs to a decision."""
    primary: Any
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionLogic:
    """Logic applied in a decision."""
    logic_type: str
    logic_source: str  # File path or config key
    logic_content: Any = None
    logic_version: str | None = None
    is_editable: bool = True


@dataclass
class DecisionResult:
    """Result of a decision."""
    outcome: DecisionOutcome
    value: Any
    confidence: float = 1.0
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    explanation: str | None = None


@dataclass
class DecisionRecord:
    """Complete record of a decision."""
    decision_id: str
    trace_id: str | None
    parent_decision_id: str | None
    
    decision_type: DecisionType
    decision_name: str
    component: str
    
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float | None
    
    inputs: DecisionInput | None
    logic: DecisionLogic | None
    result: DecisionResult | None
    
    # Type-specific details
    pattern_checks: list[PatternCheckRecord] | None = None
    llm_call: LLMCallRecord | None = None
    ha_action: HAActionRecord | None = None
    
    child_decisions: list[str] = field(default_factory=list)
    
    error: str | None = None
    error_type: str | None = None


@dataclass
class RequestTrace:
    """Complete trace of a request."""
    trace_id: str
    conversation_id: str | None
    
    # Input
    input_type: str
    input_text: str
    input_timestamp: datetime
    
    # Speaker & Context
    speaker_id: str | None
    speaker_name: str | None
    room: str | None
    
    # Processing
    status: TraceStatus
    started_at: datetime
    completed_at: datetime | None
    total_duration_ms: float | None
    
    # Classification
    intent: str | None
    intent_confidence: float
    sub_category: str | None
    
    # Routing
    routed_to_agent: str | None
    agent_used: str | None
    
    # Output
    response_text: str
    
    # Costs
    total_llm_calls: int
    total_cost_usd: float
    
    # Decisions
    decision_ids: list[str]
    
    # Feedback
    marked_as_wrong: bool = False
    correction_id: str | None = None
    
    # Error
    error: str | None = None


# ============================================================================
# CORRECTION MODELS
# ============================================================================

@dataclass
class CorrectionSuggestion:
    """A suggested fix from the AI."""
    suggestion_id: str
    suggestion_type: str
    priority: int
    
    title: str
    description: str
    impact_level: str
    
    target_logic_id: str
    current_value: Any
    proposed_value: Any
    
    diff_before: str
    diff_after: str
    
    test_inputs: list[str]
    expected_results: list[str]
    
    ai_confidence: float
    ai_reasoning: str


@dataclass
class CorrectionTestResult:
    """Result of testing a correction suggestion."""
    trace_id: str
    input_text: str
    original_result: str
    simulated_result: str
    was_wrong: bool
    status: str  # "fixed", "still_wrong", "regression", "unchanged"


@dataclass
class CorrectionAnalysis:
    """Complete analysis of an issue and proposed fixes."""
    analysis_id: str
    trace_id: str
    timestamp: datetime
    
    expected_result: str
    issue_type: IssueType
    
    root_cause: str
    root_cause_decision_id: str
    root_cause_logic_id: str
    
    similar_traces: list[str]
    suggestions: list[CorrectionSuggestion]
    
    status: CorrectionStatus
    selected_suggestion_id: str | None
    applied_at: datetime | None
    applied_by: str | None
    
    test_results: list[CorrectionTestResult] | None = None
    verification_trace_ids: list[str] = field(default_factory=list)
```

---

## 10. API Specification

### 10.1 Trace Endpoints

```python
# api/routes/pipeline.py
"""
Pipeline Management Dashboard API.
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


# ============================================================================
# TRACE ENDPOINTS
# ============================================================================

class TraceListResponse(BaseModel):
    traces: list[TraceListItem]
    total_count: int
    has_more: bool


class TraceDetailResponse(BaseModel):
    trace: RequestTrace
    decisions: list[DecisionRecord]
    decision_tree: list[DecisionTreeNode]


@router.get("/traces")
async def list_traces(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    agent: Optional[str] = None,
    speaker: Optional[str] = None,
    room: Optional[str] = None,
    marked_wrong: Optional[bool] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    search: Optional[str] = None,
) -> TraceListResponse:
    """List traces with filtering."""
    pass


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> TraceDetailResponse:
    """Get complete trace with all decisions."""
    pass


@router.post("/traces/{trace_id}/mark-wrong")
async def mark_trace_wrong(
    trace_id: str,
    expected_result: str,
    issue_type: str,
) -> dict:
    """Mark a trace as wrong and initiate correction analysis."""
    pass


@router.post("/traces/{trace_id}/rerun")
async def rerun_trace(
    trace_id: str,
    with_changes: Optional[dict] = None,
) -> TraceDetailResponse:
    """Re-run a trace, optionally with modified logic."""
    pass


# ============================================================================
# DECISION ENDPOINTS
# ============================================================================

@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str) -> DecisionRecord:
    """Get a single decision with full details."""
    pass


@router.get("/decisions/{decision_id}/logic")
async def get_decision_logic(decision_id: str) -> LogicDefinition:
    """Get the editable logic for a decision."""
    pass


# ============================================================================
# LOGIC ENDPOINTS
# ============================================================================

class LogicListResponse(BaseModel):
    logic: list[LogicDefinition]


class LogicUpdateRequest(BaseModel):
    new_content: Any
    reason: str


@router.get("/logic")
async def list_logic(
    logic_type: Optional[str] = None,
) -> LogicListResponse:
    """List all editable logic."""
    pass


@router.get("/logic/{logic_id}")
async def get_logic(logic_id: str) -> LogicDefinition:
    """Get a specific logic definition."""
    pass


@router.put("/logic/{logic_id}")
async def update_logic(
    logic_id: str,
    request: LogicUpdateRequest,
) -> LogicDefinition:
    """Update a logic definition (triggers hot-reload)."""
    pass


@router.post("/logic/{logic_id}/test")
async def test_logic(
    logic_id: str,
    test_input: str,
) -> dict:
    """Test a logic definition with sample input."""
    pass


# ============================================================================
# PATTERN ENDPOINTS
# ============================================================================

@router.get("/patterns")
async def list_patterns() -> list[PatternGroup]:
    """List all pattern groups."""
    pass


@router.get("/patterns/{group}/{pattern_name}")
async def get_pattern(
    group: str,
    pattern_name: str,
) -> PatternDefinition:
    """Get a specific pattern."""
    pass


@router.put("/patterns/{group}/{pattern_name}")
async def update_pattern(
    group: str,
    pattern_name: str,
    pattern: PatternDefinition,
) -> PatternDefinition:
    """Update a pattern."""
    pass


@router.post("/patterns/{group}")
async def create_pattern(
    group: str,
    pattern: PatternDefinition,
) -> PatternDefinition:
    """Create a new pattern."""
    pass


@router.delete("/patterns/{group}/{pattern_name}")
async def delete_pattern(
    group: str,
    pattern_name: str,
) -> dict:
    """Delete a pattern."""
    pass


@router.post("/patterns/test")
async def test_patterns(
    input_text: str,
) -> dict:
    """Test input against all patterns."""
    pass


# ============================================================================
# OVERRIDE ENDPOINTS
# ============================================================================

@router.get("/overrides")
async def list_overrides() -> list[OverrideRule]:
    """List all override rules."""
    pass


@router.post("/overrides")
async def create_override(
    override: OverrideRule,
) -> OverrideRule:
    """Create a new override rule."""
    pass


@router.put("/overrides/{name}")
async def update_override(
    name: str,
    override: OverrideRule,
) -> OverrideRule:
    """Update an override rule."""
    pass


@router.delete("/overrides/{name}")
async def delete_override(name: str) -> dict:
    """Delete an override rule."""
    pass


# ============================================================================
# CORRECTION ENDPOINTS
# ============================================================================

class AnalyzeRequest(BaseModel):
    trace_id: str
    expected_result: str
    issue_type: str


@router.post("/corrections/analyze")
async def analyze_issue(
    request: AnalyzeRequest,
) -> CorrectionAnalysis:
    """Analyze an issue and generate fix suggestions."""
    pass


@router.get("/corrections/{analysis_id}")
async def get_analysis(analysis_id: str) -> CorrectionAnalysis:
    """Get a correction analysis."""
    pass


@router.post("/corrections/{analysis_id}/test/{suggestion_id}")
async def test_suggestion(
    analysis_id: str,
    suggestion_id: str,
    historical_trace_ids: Optional[list[str]] = None,
) -> dict:
    """Test a suggestion against historical data."""
    pass


@router.post("/corrections/{analysis_id}/apply/{suggestion_id}")
async def apply_suggestion(
    analysis_id: str,
    suggestion_id: str,
) -> CorrectionAnalysis:
    """Apply a suggested fix."""
    pass


@router.post("/corrections/{analysis_id}/revert")
async def revert_correction(
    analysis_id: str,
    reason: str,
) -> CorrectionAnalysis:
    """Revert a previously applied correction."""
    pass


@router.get("/corrections/history")
async def list_corrections(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
) -> list[CorrectionAnalysis]:
    """List correction history."""
    pass
```

---

## 11. Database Schema

### 11.1 Redis Keys

```
# Traces
barnabeenet:traces:{trace_id}                    # Hash: RequestTrace
barnabeenet:traces:list                          # Sorted set: trace_ids by timestamp
barnabeenet:traces:wrong                         # Set: trace_ids marked as wrong

# Decisions
barnabeenet:decisions:{decision_id}              # Hash: DecisionRecord
barnabeenet:trace_decisions:{trace_id}           # List: decision_ids in order

# Logic
barnabeenet:logic:{logic_id}                     # Hash: LogicDefinition
barnabeenet:logic:list                           # Set: all logic_ids
barnabeenet:logic:changes                        # List: LogicChange records

# Corrections
barnabeenet:corrections:{analysis_id}            # Hash: CorrectionAnalysis
barnabeenet:corrections:list                     # Sorted set: by timestamp

# Hot-reload
barnabeenet:config_reload                        # Pub/sub channel

# Stats
barnabeenet:stats:patterns:{pattern_id}:matches  # Counter
barnabeenet:stats:patterns:{pattern_id}:fps      # Counter (false positives)
barnabeenet:stats:overrides:{name}:triggers      # Counter
```

---

## 12. Implementation Phases

### Phase 1: Enhanced Decision Logging (Week 1-2)

**Goal:** Capture every decision with full context

- [ ] Implement `DecisionRegistry` class
- [ ] Implement `DecisionContext` context manager
- [ ] Implement `DecisionLogger` for Redis persistence
- [ ] Update `MetaAgent` to use decision registry for all pattern checks
- [ ] Update `ActionAgent` to log entity resolution and service calls
- [ ] Update `InteractionAgent` to log LLM calls with full prompts
- [ ] Add decision_ids tracking to RequestTrace

**Deliverable:** Every request generates a complete decision trail viewable via API

### Phase 2: Dashboard Trace View (Week 3-4)

**Goal:** View complete pipeline timeline in the dashboard

- [ ] Build trace list component with filtering
- [ ] Build trace detail view with timeline
- [ ] Build decision tree component (expandable nodes)
- [ ] Build pattern check visualization
- [ ] Build LLM call inspector (prompt/response viewer)
- [ ] Build HA action viewer (before/after state)
- [ ] Add waterfall timeline visualization

**Deliverable:** Full pipeline visibility in the dashboard

### Phase 3: Logic Registry & Editor (Week 5-6)

**Goal:** Make all logic editable via dashboard

- [ ] Implement `LogicRegistry` class
- [ ] Create configuration file structure (patterns.yaml, routing.yaml, etc.)
- [ ] Build pattern editor UI with regex testing
- [ ] Build routing rules editor UI
- [ ] Build override rules editor UI with condition builder
- [ ] Implement hot-reload system
- [ ] Add version tracking for logic changes

**Deliverable:** All patterns, rules, and prompts editable via dashboard with hot-reload

### Phase 4: AI Correction Assistant (Week 7-8)

**Goal:** AI-powered diagnosis and fix suggestions

- [ ] Implement `AICorrectionAssistant` class
- [ ] Build "Mark as Wrong" workflow
- [ ] Build AI analysis prompt engineering
- [ ] Build suggestion generation logic
- [ ] Build diff visualization for proposed changes
- [ ] Implement regression testing against historical traces
- [ ] Build correction history and analytics

**Deliverable:** AI can analyze issues and propose tested fixes

### Phase 5: Integration & Polish (Week 9-10)

**Goal:** Production-ready system

- [ ] End-to-end testing of complete workflow
- [ ] Performance optimization (caching, batch operations)
- [ ] Mobile-responsive dashboard
- [ ] Documentation and tooltips
- [ ] Backup/restore for logic configurations
- [ ] Analytics dashboard (correction success rates, common issues)

**Deliverable:** Production-ready Pipeline Management Dashboard

---

## 13. Code Examples

### 13.1 Using Decision Registry in Meta Agent

```python
# agents/meta_agent.py (updated)

class MetaAgent(Agent):
    """Meta Agent with full decision logging."""
    
    def __init__(
        self,
        decision_registry: DecisionRegistry,
        logic_registry: LogicRegistry,
        # ... other deps
    ):
        self.decisions = decision_registry
        self.logic = logic_registry
        # ...
    
    async def classify(
        self,
        text: str,
        trace_id: str,
        context: dict | None = None,
    ) -> ClassificationResult:
        """Classify with full decision logging."""
        
        # 1. Check emergency patterns
        async with self.decisions.decision(
            name="meta.check_emergency_patterns",
            decision_type=DecisionType.PATTERN_MATCH,
            trace_id=trace_id,
            component="meta_agent",
        ) as decision:
            # Get patterns from logic registry
            patterns = await self.logic.get_logic("patterns.emergency")
            
            decision.set_inputs(primary=text)
            decision.set_logic(
                logic_type="pattern",
                logic_source="patterns.emergency",
                logic_content=[p["pattern"] for p in patterns.content["patterns"]],
            )
            
            # Check each pattern
            pattern_checks = []
            match_result = None
            
            for i, pattern_def in enumerate(patterns.content["patterns"]):
                check = PatternCheckRecord(
                    pattern_name=pattern_def["name"],
                    pattern=pattern_def["pattern"],
                    group="emergency",
                    check_order=i,
                    matched=False,
                )
                
                match = re.match(pattern_def["pattern"], text, re.IGNORECASE)
                if match:
                    check.matched = True
                    check.match_groups = list(match.groups())
                    match_result = pattern_def
                    pattern_checks.append(check)
                    break  # Stop on first match
                
                pattern_checks.append(check)
            
            # Record all pattern checks for visibility
            decision._record.pattern_checks = pattern_checks
            
            if match_result:
                decision.set_result(
                    outcome=DecisionOutcome.MATCH,
                    value={
                        "pattern_name": match_result["name"],
                        "sub_category": match_result["sub_category"],
                    },
                    confidence=1.0,  # Exact pattern match
                    explanation=f"Matched emergency pattern: {match_result['name']}",
                )
                return ClassificationResult(
                    intent=IntentCategory.EMERGENCY,
                    confidence=1.0,
                    sub_category=match_result["sub_category"],
                    target_agent="action",
                    priority=10,
                )
            else:
                decision.set_result(
                    outcome=DecisionOutcome.NO_MATCH,
                    value=None,
                    explanation="No emergency patterns matched",
                )
        
        # 2. Check instant patterns (similar pattern)
        # ...
        
        # 3. Check action patterns (similar pattern)
        # ...
        
        # 4. Fall back to LLM classification
        async with self.decisions.decision(
            name="meta.llm_classify",
            decision_type=DecisionType.LLM_CALL,
            trace_id=trace_id,
            component="meta_agent",
        ) as decision:
            prompt_template = await self.logic.get_logic("prompts.meta.classify")
            
            decision.set_inputs(primary=text, speaker=context.get("speaker"))
            decision.set_logic(
                logic_type="prompt",
                logic_source="prompts.meta.classify",
                logic_content=prompt_template.content[:500] + "...",  # Truncate for storage
            )
            
            # Render prompt
            rendered_prompt = self.jinja.render(
                prompt_template.content,
                ctx={"text": text, **context},
            )
            
            # Call LLM
            start = time.perf_counter()
            response = await self.llm.complete(
                model=self.config.classification_model,
                messages=[{"role": "user", "content": rendered_prompt}],
                temperature=0.3,
            )
            latency = (time.perf_counter() - start) * 1000
            
            # Record LLM call details
            decision._record.llm_call = LLMCallRecord(
                model=self.config.classification_model,
                provider="openrouter",
                temperature=0.3,
                max_tokens=200,
                system_prompt="",
                user_message=rendered_prompt,
                response=response.content,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                cost_usd=response.cost,
                latency_ms=latency,
            )
            
            # Parse response
            result = json.loads(response.content)
            
            decision.set_result(
                outcome=DecisionOutcome.SELECTED,
                value=result,
                confidence=result.get("confidence", 0.7),
                explanation=f"LLM classified as: {result['classification']}",
            )
            
            return ClassificationResult(
                intent=IntentCategory(result["classification"]),
                confidence=result.get("confidence", 0.7),
                sub_category=result.get("sub_category"),
                target_agent=self._get_target_agent(result["classification"]),
            )
```

### 13.2 Dashboard Frontend Component

```typescript
// pages/PipelineManager.tsx

import React, { useState, useEffect } from 'react';
import { TraceList } from '../components/TraceList';
import { TraceDetail } from '../components/TraceDetail';
import { CorrectionModal } from '../components/CorrectionModal';
import { LogicEditor } from '../components/LogicEditor';

export const PipelineManager: React.FC = () => {
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<TraceDetailResponse | null>(null);
  const [showCorrection, setShowCorrection] = useState(false);
  const [editingLogic, setEditingLogic] = useState<string | null>(null);
  
  // Filters
  const [filters, setFilters] = useState({
    status: null,
    agent: null,
    speaker: null,
    room: null,
    markedWrong: null,
    search: '',
  });

  useEffect(() => {
    loadTraces();
  }, [filters]);

  useEffect(() => {
    if (selectedTrace) {
      loadTraceDetail(selectedTrace);
    }
  }, [selectedTrace]);

  const loadTraces = async () => {
    const response = await fetch(
      `/api/v1/pipeline/traces?${new URLSearchParams(filters as any)}`
    );
    const data = await response.json();
    setTraces(data.traces);
  };

  const loadTraceDetail = async (traceId: string) => {
    const response = await fetch(`/api/v1/pipeline/traces/${traceId}`);
    const data = await response.json();
    setTraceDetail(data);
  };

  const handleMarkWrong = async (traceId: string) => {
    setSelectedTrace(traceId);
    setShowCorrection(true);
  };

  const handleEditLogic = (logicId: string) => {
    setEditingLogic(logicId);
  };

  return (
    <div className="pipeline-manager">
      <header className="pipeline-header">
        <h1>🐝 BarnabeeNet Pipeline Manager</h1>
      </header>

      <div className="pipeline-content">
        {/* Trace List */}
        <section className="trace-list-section">
          <TraceList
            traces={traces}
            filters={filters}
            onFilterChange={setFilters}
            onSelectTrace={setSelectedTrace}
            onMarkWrong={handleMarkWrong}
            selectedTraceId={selectedTrace}
          />
        </section>

        {/* Trace Detail */}
        {traceDetail && (
          <section className="trace-detail-section">
            <TraceDetail
              trace={traceDetail.trace}
              decisions={traceDetail.decisions}
              decisionTree={traceDetail.decision_tree}
              onMarkWrong={() => handleMarkWrong(traceDetail.trace.trace_id)}
              onEditLogic={handleEditLogic}
            />
          </section>
        )}
      </div>

      {/* Correction Modal */}
      {showCorrection && selectedTrace && (
        <CorrectionModal
          traceId={selectedTrace}
          onClose={() => setShowCorrection(false)}
          onApplied={() => {
            setShowCorrection(false);
            loadTraces();
            loadTraceDetail(selectedTrace);
          }}
        />
      )}

      {/* Logic Editor Modal */}
      {editingLogic && (
        <LogicEditor
          logicId={editingLogic}
          onClose={() => setEditingLogic(null)}
          onSaved={() => {
            setEditingLogic(null);
            // Trigger refresh
          }}
        />
      )}
    </div>
  );
};
```

---

## Summary

This document specifies a **complete, production-ready Pipeline Management Dashboard** for BarnabeeNet that provides:

1. **Full Trace Visibility** - See every decision made for every request
2. **Editable Logic** - All patterns, prompts, and rules stored as data, not code
3. **AI-Assisted Correction** - When things go wrong, AI diagnoses and proposes fixes
4. **Hot-Reload** - Changes take effect immediately without restart
5. **Regression Testing** - Test fixes against historical data before applying

The key architectural insight is the **Decision Registry** - every logical branch registers its inputs, logic, and outputs, making the entire system transparent and editable.

This transforms BarnabeeNet from a black-box AI assistant into a **self-improving, fully observable system** where you can understand exactly why any decision was made and fix it when needed.
