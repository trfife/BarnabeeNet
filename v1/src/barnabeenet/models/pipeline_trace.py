"""Pipeline Trace Model for enhanced observability.

Captures detailed decision information through the request processing pipeline
for display in the dashboard chat tab.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PipelineTrace:
    """Complete trace of a request through the pipeline.

    This model captures all decision details for displaying in the dashboard:
    - Meta Agent classification and routing
    - Context enrichment and memory retrieval
    - Action parsing and target resolution
    - LLM calls if made
    - Final response details
    """

    # Request identification
    request_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Input
    raw_input: str = ""
    speaker: str | None = None
    speaker_location: str | None = None

    # Meta Agent decisions
    meta_classification: dict[str, Any] = field(default_factory=dict)
    # {intent, confidence, sub_category}
    meta_routing_reason: str = ""  # Human-readable explanation
    meta_pattern_matched: str | None = None  # Which pattern triggered
    meta_processing_time_ms: float = 0.0

    # Context enrichment
    context_evaluation: dict[str, Any] | None = None
    # {mood, urgency, empathy_needed}
    memory_queries_generated: list[str] = field(default_factory=list)
    memories_retrieved: list[dict[str, Any]] = field(default_factory=list)

    # Action Agent (if routed there)
    parsed_segments: list[dict[str, Any]] | None = None  # Compound command segments
    resolved_targets: list[dict[str, Any]] | None = None  # How targets were resolved
    service_calls_generated: list[dict[str, Any]] | None = None
    actions_executed: list[dict[str, Any]] | None = None  # Execution results

    # Timer (if created)
    timer_created: dict[str, Any] | None = None

    # LLM call (if made)
    llm_model_used: str | None = None
    llm_prompt_summary: str | None = None  # Summary of what was sent
    llm_tokens_in: int | None = None
    llm_tokens_out: int | None = None
    llm_latency_ms: float | None = None

    # Final output
    response_text: str = ""
    response_agent: str = ""  # Which agent produced the response
    total_latency_ms: float = 0.0

    # Error tracking
    error: str | None = None
    error_details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "input": {
                "text": self.raw_input,
                "speaker": self.speaker,
                "location": self.speaker_location,
            },
            "meta_agent": {
                "classification": self.meta_classification,
                "routing_reason": self.meta_routing_reason,
                "pattern_matched": self.meta_pattern_matched,
                "processing_time_ms": self.meta_processing_time_ms,
            },
            "context": {
                "evaluation": self.context_evaluation,
                "memory_queries": self.memory_queries_generated,
                "memories_retrieved": len(self.memories_retrieved),
                "memories": self.memories_retrieved,
            },
            "action": {
                "parsed_segments": self.parsed_segments,
                "resolved_targets": self.resolved_targets,
                "service_calls": self.service_calls_generated,
                "executed": self.actions_executed,
            }
            if self.parsed_segments is not None
            else None,
            "timer": self.timer_created,
            "llm": {
                "model": self.llm_model_used,
                "prompt_summary": self.llm_prompt_summary,
                "tokens_in": self.llm_tokens_in,
                "tokens_out": self.llm_tokens_out,
                "latency_ms": self.llm_latency_ms,
            }
            if self.llm_model_used
            else None,
            "response": {
                "text": self.response_text,
                "agent": self.response_agent,
            },
            "latency_ms": self.total_latency_ms,
            "error": self.error,
            "error_details": self.error_details,
        }

    @classmethod
    def from_orchestrator_response(
        cls,
        request_id: str,
        input_text: str,
        speaker: str | None,
        room: str | None,
        response: dict[str, Any],
    ) -> PipelineTrace:
        """Create a PipelineTrace from orchestrator response data.

        Args:
            request_id: Request ID
            input_text: Original input text
            speaker: Speaker ID
            room: Room/location
            response: Orchestrator response dict

        Returns:
            PipelineTrace with data extracted from response
        """
        trace = cls(
            request_id=request_id,
            raw_input=input_text,
            speaker=speaker,
            speaker_location=room,
        )

        # Extract classification info
        if "intent" in response:
            trace.meta_classification = {
                "intent": response.get("intent"),
                "confidence": response.get("intent_confidence"),
                "sub_category": response.get("sub_category"),
            }

        # Extract routing reason
        if "routing_reason" in response:
            trace.meta_routing_reason = response["routing_reason"]
        elif "intent" in response:
            # Generate default routing reason
            intent = response.get("intent", "unknown")
            confidence = response.get("intent_confidence", 0)
            trace.meta_routing_reason = f"Routed to {intent} (confidence: {confidence:.0%})"

        # Extract memory info
        if "memories_retrieved" in response:
            trace.memories_retrieved = response.get("memories_retrieved_data", [])

        # Extract action info
        if "actions" in response and response["actions"]:
            trace.actions_executed = response["actions"]
            # Try to extract parsed segments from action data
            if isinstance(response["actions"], list):
                trace.service_calls_generated = [
                    {
                        "service": a.get("service"),
                        "entity_id": a.get("entity_id"),
                        "area_id": a.get("target_area"),
                    }
                    for a in response["actions"]
                ]

        # Extract LLM info
        llm_details = response.get("llm_details")
        if llm_details:
            trace.llm_model_used = llm_details.get("model")
            trace.llm_tokens_in = llm_details.get("input_tokens")
            trace.llm_tokens_out = llm_details.get("output_tokens")
            trace.llm_latency_ms = llm_details.get("llm_latency_ms")
            # Create a summary of the prompt
            if llm_details.get("messages_sent"):
                messages = llm_details["messages_sent"]
                if isinstance(messages, list) and len(messages) > 0:
                    last_user_msg = None
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            last_user_msg = msg.get("content", "")[:100]
                            break
                    trace.llm_prompt_summary = last_user_msg

        # Extract response
        trace.response_text = response.get("response", "")
        trace.response_agent = response.get("agent", response.get("agent_used", "unknown"))
        trace.total_latency_ms = response.get("latency_ms", 0)

        # Extract errors
        if "error" in response:
            error_info = response["error"]
            if isinstance(error_info, dict):
                trace.error = error_info.get("message", str(error_info))
                trace.error_details = error_info
            else:
                trace.error = str(error_info)

        return trace


@dataclass
class RoutingDecision:
    """Details about a routing decision from MetaAgent."""

    intent: str
    confidence: float
    sub_category: str | None = None
    reason: str = ""  # Human-readable explanation
    pattern_matched: str | None = None  # Which pattern triggered
    target_agent: str = ""
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "sub_category": self.sub_category,
            "reason": self.reason,
            "pattern_matched": self.pattern_matched,
            "target_agent": self.target_agent,
            "processing_time_ms": self.processing_time_ms,
        }


def generate_routing_reason(
    intent: str,
    confidence: float,
    pattern_matched: str | None = None,
    sub_category: str | None = None,
) -> str:
    """Generate a human-readable routing reason.

    Args:
        intent: Classified intent
        confidence: Classification confidence
        pattern_matched: Pattern that matched (if any)
        sub_category: Sub-category (if any)

    Returns:
        Human-readable explanation
    """
    if intent == "instant":
        if sub_category:
            return f"Instant: {sub_category} query (confidence: {confidence:.0%})"
        return f"Instant: Quick response query (confidence: {confidence:.0%})"

    if intent == "action":
        if pattern_matched:
            return f"Action: Matched '{pattern_matched}' pattern (confidence: {confidence:.0%})"
        return f"Action: Device control command (confidence: {confidence:.0%})"

    if intent == "memory":
        if sub_category == "store":
            return f"Memory: Store operation (confidence: {confidence:.0%})"
        elif sub_category == "recall":
            return f"Memory: Recall operation (confidence: {confidence:.0%})"
        return f"Memory: Memory operation (confidence: {confidence:.0%})"

    if intent in ("conversation", "query"):
        return f"Interaction: Conversational query (confidence: {confidence:.0%})"

    if intent == "emergency":
        return f"Emergency: Safety-critical request (confidence: {confidence:.0%})"

    return f"Routed to {intent} (confidence: {confidence:.0%})"


__all__ = [
    "PipelineTrace",
    "RoutingDecision",
    "generate_routing_reason",
]
