"""AI Correction Service - Diagnoses issues and proposes fixes.

This service analyzes traces where things went wrong and uses AI to:
1. Diagnose the root cause
2. Suggest specific fixes
3. Test fixes against historical data
4. Apply fixes with hot-reload

Now enhanced with LogicDiagnostics for pattern-level analysis.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as redis

    from barnabeenet.services.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# In-memory storage for analyses (would be Redis in production)
_analyses: dict[str, CorrectionAnalysis] = {}


@dataclass
class CorrectionSuggestion:
    """A suggested fix for an issue."""

    suggestion_id: str
    suggestion_type: str  # "pattern_add", "pattern_modify", "entity_alias", etc.
    title: str
    description: str
    impact_level: str  # "low", "medium", "high"
    target_logic_id: str
    proposed_value: str | None = None
    diff_before: str | None = None
    diff_after: str | None = None
    confidence: float = 0.0
    reasoning: str | None = None
    test_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "suggestion_type": self.suggestion_type,
            "title": self.title,
            "description": self.description,
            "impact_level": self.impact_level,
            "target_logic_id": self.target_logic_id,
            "proposed_value": self.proposed_value,
            "diff_before": self.diff_before,
            "diff_after": self.diff_after,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class CorrectionAnalysis:
    """Complete analysis of why a request failed and how to fix it."""

    analysis_id: str
    trace_id: str
    timestamp: datetime
    expected_result: str
    issue_type: str
    root_cause: str
    root_cause_logic_id: str | None = None
    suggestions: list[CorrectionSuggestion] = field(default_factory=list)
    applied_at: datetime | None = None
    applied_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "trace_id": self.trace_id,
            "root_cause": self.root_cause,
            "root_cause_logic_id": self.root_cause_logic_id,
            "suggestions": [s.to_dict() for s in self.suggestions],
        }


# AI analysis prompt
ANALYSIS_PROMPT = """You are an expert at debugging BarnabeeNet's home assistant pipeline.

## Your Task
Analyze this request trace and determine why it produced the wrong result.

## Request Information
- Input: "{input_text}"
- Expected result: "{expected_result}"
- Actual result: "{actual_result}"
- Issue type: "{issue_type}"
- Agent used: {agent_used}
- Intent classified: {intent}

## Pipeline Signals
{signals_info}

## Home Assistant Actions (if any)
{ha_actions}

## Analysis Required
1. Identify the ROOT CAUSE - what specific decision led to the wrong outcome?
2. Explain WHY this happened
3. Suggest 1-3 SPECIFIC fixes, each with:
   - Type: pattern_modify, entity_alias, routing_change, or prompt_edit
   - What to change and why
   - Impact level (low = only this case, high = affects many)
   - Confidence (0-1)

## Response Format
Respond with valid JSON only:
{{
  "root_cause": "Brief description of what went wrong",
  "root_cause_logic_id": "patterns.action.device_control or similar",
  "suggestions": [
    {{
      "suggestion_type": "pattern_modify|entity_alias|routing_change|prompt_edit",
      "title": "Brief title",
      "description": "What this fix does",
      "impact_level": "low|medium|high",
      "target_logic_id": "config location to modify",
      "proposed_change": "The new value or config",
      "reasoning": "Why this fix will work",
      "confidence": 0.85
    }}
  ]
}}"""


class AICorrectionService:
    """AI-powered assistant for diagnosing and fixing pipeline issues."""

    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client
        self._llm_client: OpenRouterClient | None = None

    async def _get_llm_client(self) -> OpenRouterClient | None:
        """Get or create the LLM client."""
        if self._llm_client is None:
            from barnabeenet.services.llm.openrouter import OpenRouterClient
            from barnabeenet.services.secrets import get_secrets_service

            if self._redis is None:
                logger.warning("No Redis client - cannot fetch API key for LLM")
                return None

            secrets = await get_secrets_service(self._redis)
            api_key = await secrets.get_secret("openrouter_api_key")
            if api_key:
                self._llm_client = OpenRouterClient(api_key=api_key)
        return self._llm_client

    async def analyze_trace(
        self,
        trace_id: str,
        expected_result: str,
        issue_type: str,
    ) -> CorrectionAnalysis:
        """Analyze a trace and generate fix suggestions."""
        from barnabeenet.services.pipeline_signals import get_pipeline_logger

        # Get the trace
        pipeline_logger = get_pipeline_logger()
        trace = await pipeline_logger.get_trace_by_id(trace_id)
        if not trace:
            raise ValueError(f"Trace not found: {trace_id}")

        # Format signals for prompt
        signals_info = self._format_signals([s.model_dump() for s in trace.signals])
        ha_actions = self._format_ha_actions(trace.ha_actions)

        # Build prompt
        prompt = ANALYSIS_PROMPT.format(
            input_text=trace.input_text or "",
            expected_result=expected_result,
            actual_result=trace.response_text or "",
            issue_type=issue_type,
            agent_used=trace.agent_used or "unknown",
            intent=trace.intent or "unknown",
            signals_info=signals_info,
            ha_actions=ha_actions,
        )

        # Call LLM
        llm_client = await self._get_llm_client()
        if not llm_client:
            # No LLM available - return basic analysis
            return self._create_basic_analysis(
                trace_id, expected_result, issue_type, trace.model_dump()
            )

        try:
            response = await llm_client.simple_chat(
                user_message=prompt,
                agent_type="meta",  # Use fast model for analysis
            )

            # Parse AI response
            content = response.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            analysis_data = json.loads(content)

            # Build suggestions
            suggestions = []
            for i, sugg_data in enumerate(analysis_data.get("suggestions", [])):
                suggestions.append(
                    CorrectionSuggestion(
                        suggestion_id=f"sugg_{trace_id[:8]}_{i}",
                        suggestion_type=sugg_data.get("suggestion_type", "other"),
                        title=sugg_data.get("title", "Suggested fix"),
                        description=sugg_data.get("description", ""),
                        impact_level=sugg_data.get("impact_level", "medium"),
                        target_logic_id=sugg_data.get("target_logic_id", ""),
                        proposed_value=sugg_data.get("proposed_change"),
                        diff_before=self._get_current_value(sugg_data.get("target_logic_id")),
                        diff_after=sugg_data.get("proposed_change"),
                        confidence=sugg_data.get("confidence", 0.5),
                        reasoning=sugg_data.get("reasoning"),
                    )
                )

            analysis = CorrectionAnalysis(
                analysis_id=f"analysis_{uuid.uuid4().hex[:12]}",
                trace_id=trace_id,
                timestamp=datetime.now(UTC),
                expected_result=expected_result,
                issue_type=issue_type,
                root_cause=analysis_data.get("root_cause", "Unknown"),
                root_cause_logic_id=analysis_data.get("root_cause_logic_id"),
                suggestions=suggestions,
            )

            # Store for later reference
            _analyses[analysis.analysis_id] = analysis

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return self._create_basic_analysis(
                trace_id, expected_result, issue_type, trace.model_dump()
            )
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._create_basic_analysis(
                trace_id, expected_result, issue_type, trace.model_dump()
            )

    def _create_basic_analysis(
        self,
        trace_id: str,
        expected_result: str,
        issue_type: str,
        trace: dict[str, Any],
    ) -> CorrectionAnalysis:
        """Create a basic analysis when AI is unavailable.

        Enhanced to use LogicDiagnostics for pattern-level insights.
        """
        issue_descriptions = {
            "wrong_entity": "The system selected the wrong device or entity",
            "wrong_action": "The system performed an incorrect action",
            "wrong_routing": "The request was routed to the wrong agent",
            "clarification_needed": "The system should have asked for clarification",
            "tone_content": "The response tone or content was inappropriate",
            "other": "An unspecified issue occurred",
        }

        suggestions = []
        input_text = trace.get("input_text", "")

        # Use LogicDiagnostics for pattern-level analysis if available
        diagnostics_info = self._get_pattern_diagnostics(input_text)

        # Generate suggestions based on issue type and diagnostics
        if issue_type == "wrong_entity":
            suggestions.append(
                CorrectionSuggestion(
                    suggestion_id=f"sugg_{trace_id[:8]}_0",
                    suggestion_type="entity_alias",
                    title="Add entity alias",
                    description="Add an alias to help the system find the correct entity",
                    impact_level="low",
                    target_logic_id="config/overrides.yaml#entity_aliases",
                    proposed_value="# Add alias for the target entity",
                    confidence=0.7,
                    reasoning="Adding an alias helps with entity resolution",
                )
            )
        elif issue_type == "wrong_routing":
            # Use diagnostics to suggest better patterns
            if diagnostics_info:
                # Add diagnostic-based suggestions
                if diagnostics_info.get("near_misses"):
                    for i, nm in enumerate(diagnostics_info["near_misses"][:2]):
                        suggestions.append(
                            CorrectionSuggestion(
                                suggestion_id=f"sugg_{trace_id[:8]}_{i}",
                                suggestion_type="pattern_modify",
                                title=f"Modify near-miss pattern: {nm.get('group', 'unknown')}",
                                description=f"Pattern '{nm.get('pattern', '')[:50]}...' almost matched (similarity={nm.get('similarity_score', 0):.2f}). Reason: {nm.get('failure_reason', 'unknown')}",
                                impact_level="medium",
                                target_logic_id=f"config/patterns.yaml#{nm.get('group', '')}",
                                proposed_value=nm.get(
                                    "suggestion", "Modify pattern to match this input"
                                ),
                                confidence=nm.get("similarity_score", 0.5),
                                reasoning=f"Pattern was close to matching. Suggestions: {', '.join(nm.get('suggestions', [])[:2]) or 'Review pattern'}",
                            )
                        )

                if diagnostics_info.get("suggested_patterns"):
                    for i, pattern in enumerate(diagnostics_info["suggested_patterns"][:2]):
                        suggestions.append(
                            CorrectionSuggestion(
                                suggestion_id=f"sugg_{trace_id[:8]}_new_{i}",
                                suggestion_type="pattern_add",
                                title="Add new pattern for this input",
                                description=f"Suggested pattern: {pattern}",
                                impact_level="low",
                                target_logic_id="config/patterns.yaml#action",
                                proposed_value=pattern,
                                confidence=0.6,
                                reasoning="Generated pattern based on input structure",
                            )
                        )

                # Diagnostics summary already used in suggestion descriptions
            else:
                suggestions.append(
                    CorrectionSuggestion(
                        suggestion_id=f"sugg_{trace_id[:8]}_0",
                        suggestion_type="pattern_modify",
                        title="Adjust routing pattern",
                        description="Modify pattern to better match this type of request",
                        impact_level="medium",
                        target_logic_id="config/patterns.yaml",
                        proposed_value=f"# Add or modify pattern for: {input_text}",
                        confidence=0.6,
                        reasoning="A more specific pattern would capture this intent correctly",
                    )
                )

        elif issue_type == "wrong_action":
            suggestions.append(
                CorrectionSuggestion(
                    suggestion_id=f"sugg_{trace_id[:8]}_0",
                    suggestion_type="pattern_modify",
                    title="Adjust action pattern",
                    description="The action pattern may be too broad or incorrect",
                    impact_level="medium",
                    target_logic_id="config/patterns.yaml#action",
                    proposed_value=f"# Review action patterns for: {input_text}",
                    confidence=0.5,
                    reasoning="Action was misinterpreted - pattern needs refinement",
                )
            )

        analysis = CorrectionAnalysis(
            analysis_id=f"analysis_{uuid.uuid4().hex[:12]}",
            trace_id=trace_id,
            timestamp=datetime.now(UTC),
            expected_result=expected_result,
            issue_type=issue_type,
            root_cause=issue_descriptions.get(issue_type, "Unknown issue")
            if not diagnostics_info
            else f"{issue_descriptions.get(issue_type, 'Unknown issue')}. Pattern diagnostics available.",
            root_cause_logic_id=None,
            suggestions=suggestions,
        )

        _analyses[analysis.analysis_id] = analysis
        return analysis

    def _get_pattern_diagnostics(self, text: str) -> dict[str, Any] | None:
        """Get pattern diagnostics for input text.

        Returns diagnostic info including near-misses and suggestions.
        """
        if not text:
            return None

        try:
            import re

            from barnabeenet.agents.meta import (
                ACTION_PATTERNS,
                INSTANT_PATTERNS,
                MEMORY_PATTERNS,
                QUERY_PATTERNS,
            )
            from barnabeenet.services.logic_diagnostics import get_diagnostics_service

            diagnostics = get_diagnostics_service()

            # Use hardcoded patterns for diagnostics
            compiled_patterns = {
                "instant": [(re.compile(p, re.IGNORECASE), c) for p, c in INSTANT_PATTERNS],
                "action": [(re.compile(p, re.IGNORECASE), c) for p, c in ACTION_PATTERNS],
                "memory": [(re.compile(p, re.IGNORECASE), c) for p, c in MEMORY_PATTERNS],
                "query": [(re.compile(p, re.IGNORECASE), c) for p, c in QUERY_PATTERNS],
            }

            pattern_priority = [
                ("instant", "INSTANT", 0.95),
                ("action", "ACTION", 0.90),
                ("memory", "MEMORY", 0.90),
                ("query", "QUERY", 0.85),
            ]

            diag = diagnostics.diagnose_pattern_match(
                text=text,
                compiled_patterns=compiled_patterns,
                pattern_priority=pattern_priority,
            )

            return {
                "total_checked": diag.total_patterns_checked,
                "near_misses": [
                    {
                        "pattern": nm.pattern_str,
                        "group": nm.pattern_group,
                        "sub_category": nm.sub_category,
                        "similarity_score": nm.similarity_score,
                        "failure_reason": nm.failure_reason.value if nm.failure_reason else None,
                        "suggestions": nm.suggestions,
                    }
                    for nm in diag.near_misses[:5]
                ],
                "suggested_patterns": diag.suggested_patterns[:3],
                "suggested_modifications": diag.suggested_modifications[:3],
            }

        except Exception as e:
            logger.debug(f"Pattern diagnostics failed: {e}")
            return None

    def _format_signals(self, signals: list[dict]) -> str:
        """Format signals for the prompt."""
        if not signals:
            return "No signals recorded"

        lines = []
        for sig in signals:
            line = f"- {sig.get('signal_type', 'unknown')}: {sig.get('summary', '')}"
            if sig.get("latency_ms"):
                line += f" ({sig['latency_ms']:.1f}ms)"
            if sig.get("model_used"):
                line += f" [model: {sig['model_used']}]"
            lines.append(line)

        return "\n".join(lines)

    def _format_ha_actions(self, actions: list[dict]) -> str:
        """Format HA actions for the prompt."""
        if not actions:
            return "No Home Assistant actions"

        lines = []
        for action in actions:
            service = action.get("service") or action.get("action_type", "unknown")
            entity = action.get("entity_id", "")
            lines.append(f"- {service} → {entity}")

        return "\n".join(lines)

    def _get_current_value(self, logic_id: str | None) -> str | None:
        """Get current value for a logic ID."""
        # TODO: Actually fetch from LogicRegistry
        if not logic_id:
            return None
        return f"# Current value for {logic_id}"

    async def test_suggestion(
        self,
        analysis_id: str,
        suggestion_id: str,
    ) -> dict[str, Any]:
        """Test a suggestion against historical data."""
        analysis = _analyses.get(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        suggestion = next(
            (s for s in analysis.suggestions if s.suggestion_id == suggestion_id),
            None,
        )
        if not suggestion:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        # For now, return simulated test results
        # TODO: Actually replay historical traces with the proposed change
        return {
            "suggestion_id": suggestion_id,
            "test_results": [],
            "would_fix_original": True,
            "regression_count": 0,
            "improvement_count": 1,
        }

    async def apply_suggestion(
        self,
        analysis_id: str,
        suggestion_id: str,
        user: str,
    ) -> CorrectionAnalysis:
        """Apply a suggested fix."""
        analysis = _analyses.get(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        suggestion = next(
            (s for s in analysis.suggestions if s.suggestion_id == suggestion_id),
            None,
        )
        if not suggestion:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        # TODO: Actually apply the change to LogicRegistry
        logger.info(
            f"Applying suggestion {suggestion_id}",
            extra={
                "target": suggestion.target_logic_id,
                "type": suggestion.suggestion_type,
                "user": user,
            },
        )

        analysis.applied_at = datetime.now(UTC)
        analysis.applied_by = user

        return analysis


# Singleton instance
_correction_service: AICorrectionService | None = None


async def get_correction_service() -> AICorrectionService:
    """Get the singleton correction service instance."""
    global _correction_service
    if _correction_service is None:
        _correction_service = AICorrectionService()
    return _correction_service
