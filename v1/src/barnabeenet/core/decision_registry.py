"""Decision Registry - The foundation of observable, traceable logic.

Every logical choice in BarnabeeNet registers here. This enables:
1. Complete tracing of all decisions
2. UI-based viewing of decision chains
3. AI-assisted corrections with full context
4. Historical analysis and debugging

The Decision Registry captures:
- What decision was made
- What inputs led to that decision
- What logic was applied
- What the outcome was
- How long it took
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


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
    MEMORY_RETRIEVAL = "memory_retrieval"
    MEMORY_STORAGE = "memory_storage"
    CONTEXT_EVALUATION = "context_evaluation"


class DecisionOutcome(Enum):
    """Possible outcomes of a decision."""

    MATCH = "match"
    NO_MATCH = "no_match"
    SELECTED = "selected"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    ERROR = "error"
    OVERRIDDEN = "overridden"
    FALLBACK = "fallback"


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
    logic_content: str | dict | None = None  # The actual logic (pattern, prompt, etc.)
    logic_version: str | None = None  # Version hash for tracking changes
    is_editable: bool = True  # Can this logic be edited via UI?


@dataclass
class DecisionResult:
    """The result of a decision."""

    outcome: DecisionOutcome
    value: Any  # The actual result value
    confidence: float = 1.0
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    explanation: str | None = None  # Human-readable explanation


@dataclass
class DecisionRecord:
    """Complete record of a decision for logging and analysis."""

    # Identification
    decision_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:8]}")
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
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API/storage."""
        return {
            "decision_id": self.decision_id,
            "trace_id": self.trace_id,
            "parent_decision_id": self.parent_decision_id,
            "decision_type": self.decision_type.value,
            "decision_name": self.decision_name,
            "component": self.component,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "inputs": (
                {
                    "primary": str(self.inputs.primary)[:200],  # Truncate for storage
                    "context": self.inputs.context,
                }
                if self.inputs
                else None
            ),
            "logic": (
                {
                    "logic_type": self.logic.logic_type,
                    "logic_source": self.logic.logic_source,
                    "logic_content": (
                        str(self.logic.logic_content)[:500] if self.logic.logic_content else None
                    ),
                    "is_editable": self.logic.is_editable,
                }
                if self.logic
                else None
            ),
            "result": (
                {
                    "outcome": self.result.outcome.value,
                    "value": str(self.result.value)[:200] if self.result.value else None,
                    "confidence": self.result.confidence,
                    "alternatives": self.result.alternatives[:3],  # Limit alternatives
                    "explanation": self.result.explanation,
                }
                if self.result
                else None
            ),
            "child_decisions": self.child_decisions,
            "error": self.error,
            "error_type": self.error_type,
        }


class DecisionContext:
    """Context manager for recording a decision."""

    def __init__(
        self,
        registry: DecisionRegistry,
        decision_name: str,
        decision_type: DecisionType,
        trace_id: str | None = None,
        component: str | None = None,
        parent_decision_id: str | None = None,
    ):
        self._registry = registry
        self._record = DecisionRecord(
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            decision_type=decision_type,
            decision_name=decision_name,
            component=component or "",
        )
        self._start_time = time.perf_counter()

        # For building inputs/logic/result
        self._primary_input: Any = None
        self._context: dict[str, Any] = {}
        self._logic_type: str = ""
        self._logic_source: str = ""
        self._logic_content: Any = None

    async def __aenter__(self) -> DecisionContext:
        """Enter decision context."""
        self._record.started_at = datetime.now(UTC)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit decision context and record the decision."""
        self._record.completed_at = datetime.now(UTC)
        self._record.duration_ms = (time.perf_counter() - self._start_time) * 1000

        # Build inputs if set
        if self._primary_input is not None or self._context:
            self._record.inputs = DecisionInput(
                primary=self._primary_input,
                context=self._context,
            )

        # Build logic if set
        if self._logic_type:
            self._record.logic = DecisionLogic(
                logic_type=self._logic_type,
                logic_source=self._logic_source,
                logic_content=self._logic_content,
            )

        # Handle errors
        if exc_val:
            self._record.error = str(exc_val)
            self._record.error_type = type(exc_val).__name__
            if not self._record.result:
                self._record.result = DecisionResult(
                    outcome=DecisionOutcome.ERROR,
                    value=None,
                    explanation=str(exc_val),
                )

        # Record the decision
        await self._registry.record_decision(self._record)

    def set_inputs(self, primary: Any = None, **context: Any) -> None:
        """Set the inputs to this decision."""
        self._primary_input = primary
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
        value: Any = None,
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


class DecisionRegistry:
    """Central registry for all decision points in BarnabeeNet.

    Usage:
        registry = DecisionRegistry()

        async with registry.decision(
            "meta.check_action_patterns",
            DecisionType.PATTERN_MATCH,
            trace_id="trace_123",
            component="meta_agent",
        ) as decision:
            decision.set_inputs(text, speaker=speaker, room=room)
            decision.set_logic("pattern", "config/patterns.yaml", patterns)

            # Do the actual work
            matched, pattern = check_patterns(text)

            if matched:
                decision.set_result(
                    DecisionOutcome.MATCH,
                    value=pattern.sub_category,
                    confidence=pattern.confidence,
                )
            else:
                decision.set_result(DecisionOutcome.NO_MATCH)
    """

    def __init__(self, max_decisions: int = 10000) -> None:
        """Initialize the Decision Registry.

        Args:
            max_decisions: Maximum decisions to keep in memory (rolling buffer)
        """
        self._decisions: dict[str, DecisionRecord] = {}
        self._trace_decisions: dict[str, list[str]] = {}  # trace_id -> decision_ids
        self._max_decisions = max_decisions
        self._decision_count = 0

    @asynccontextmanager
    async def decision(
        self,
        decision_name: str,
        decision_type: DecisionType,
        trace_id: str | None = None,
        component: str | None = None,
        parent_decision_id: str | None = None,
    ):
        """Create a decision context manager.

        Args:
            decision_name: Name of the decision (e.g., "meta.check_patterns")
            decision_type: Type of decision
            trace_id: ID of the parent request trace
            component: Component making the decision
            parent_decision_id: ID of parent decision if nested

        Yields:
            DecisionContext for recording the decision
        """
        ctx = DecisionContext(
            registry=self,
            decision_name=decision_name,
            decision_type=decision_type,
            trace_id=trace_id,
            component=component,
            parent_decision_id=parent_decision_id,
        )
        async with ctx:
            yield ctx

    async def record_decision(self, record: DecisionRecord) -> None:
        """Record a completed decision."""
        # Enforce max size (rolling buffer)
        if len(self._decisions) >= self._max_decisions:
            # Remove oldest 10%
            remove_count = self._max_decisions // 10
            oldest_ids = list(self._decisions.keys())[:remove_count]
            for did in oldest_ids:
                self._decisions.pop(did, None)

        self._decisions[record.decision_id] = record
        self._decision_count += 1

        # Track by trace
        if record.trace_id:
            if record.trace_id not in self._trace_decisions:
                self._trace_decisions[record.trace_id] = []
            self._trace_decisions[record.trace_id].append(record.decision_id)

        logger.debug(
            "Decision recorded: %s [%s] %s in %.1fms",
            record.decision_name,
            record.result.outcome.value if record.result else "pending",
            record.result.value if record.result else "",
            record.duration_ms or 0,
        )

    async def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)

    async def get_trace_decisions(self, trace_id: str) -> list[DecisionRecord]:
        """Get all decisions for a trace."""
        decision_ids = self._trace_decisions.get(trace_id, [])
        return [self._decisions[did] for did in decision_ids if did in self._decisions]

    async def get_recent_decisions(self, limit: int = 100) -> list[DecisionRecord]:
        """Get recent decisions."""
        decisions = list(self._decisions.values())
        return sorted(decisions, key=lambda d: d.started_at or datetime.min, reverse=True)[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        decisions = list(self._decisions.values())

        # Count by type
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        total_duration = 0.0

        for d in decisions:
            by_type[d.decision_type.value] = by_type.get(d.decision_type.value, 0) + 1
            if d.result:
                by_outcome[d.result.outcome.value] = by_outcome.get(d.result.outcome.value, 0) + 1
            if d.duration_ms:
                total_duration += d.duration_ms

        return {
            "total_decisions": self._decision_count,
            "decisions_in_memory": len(self._decisions),
            "traces_tracked": len(self._trace_decisions),
            "by_type": by_type,
            "by_outcome": by_outcome,
            "avg_duration_ms": total_duration / len(decisions) if decisions else 0,
        }

    def clear(self) -> None:
        """Clear all decisions (for testing)."""
        self._decisions.clear()
        self._trace_decisions.clear()
        self._decision_count = 0


# Singleton instance
_decision_registry: DecisionRegistry | None = None


def get_decision_registry() -> DecisionRegistry:
    """Get the singleton DecisionRegistry instance."""
    global _decision_registry
    if _decision_registry is None:
        _decision_registry = DecisionRegistry()
    return _decision_registry


def reset_decision_registry() -> None:
    """Reset the singleton (for testing)."""
    global _decision_registry
    if _decision_registry:
        _decision_registry.clear()
    _decision_registry = None
