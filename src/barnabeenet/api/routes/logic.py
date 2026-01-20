"""Logic API - Endpoints for viewing and editing BarnabeeNet logic.

This module provides the REST API for the Pipeline Management Dashboard's
"Logic Browser" feature, allowing users to:

1. View all patterns, routing rules, and overrides
2. Edit patterns without code changes
3. Test patterns against sample inputs
4. View change history
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/logic", tags=["logic"])


# =============================================================================
# Request/Response Models
# =============================================================================


class PatternDefinitionResponse(BaseModel):
    """Pattern definition for API response."""

    name: str
    pattern: str
    sub_category: str
    confidence: float
    enabled: bool
    description: str
    examples: list[str]
    typo_variants: list[str]


class PatternGroupResponse(BaseModel):
    """Pattern group for API response."""

    name: str
    patterns: dict[str, PatternDefinitionResponse]
    pattern_count: int


class RoutingRuleResponse(BaseModel):
    """Routing rule for API response."""

    intent: str
    agent: str
    description: str
    priority: int
    requires_llm: bool
    timeout_ms: int
    enabled: bool


class OverrideRuleResponse(BaseModel):
    """Override rule for API response."""

    name: str
    description: str
    enabled: bool
    condition_type: str
    conditions: dict[str, Any]
    rules: list[dict[str, Any]]


class EntityAliasResponse(BaseModel):
    """Entity alias for API response."""

    alias: str
    entity_id: str | None
    resolve_by: str | None
    domain: str | None
    priority: str


class LogicOverviewResponse(BaseModel):
    """Complete logic overview."""

    patterns: dict[str, PatternGroupResponse]
    routing: dict[str, RoutingRuleResponse]
    overrides: dict[str, OverrideRuleResponse]
    entity_aliases: dict[str, EntityAliasResponse]
    stats: dict[str, Any]
    metadata: dict[str, Any]


class PatternUpdateRequest(BaseModel):
    """Request to update a pattern."""

    pattern: str | None = None
    sub_category: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    enabled: bool | None = None
    description: str | None = None
    examples: list[str] | None = None
    reason: str = Field(..., description="Reason for the change")


class PatternTestRequest(BaseModel):
    """Request to test patterns against input."""

    text: str = Field(..., description="Input text to test")
    groups: list[str] | None = Field(
        None, description="Pattern groups to test (all if not specified)"
    )


class PatternTestResult(BaseModel):
    """Result of pattern test."""

    group: str
    pattern_name: str
    pattern: str
    sub_category: str
    matched: bool
    match_groups: list[str] | None
    confidence: float


class PatternTestResponse(BaseModel):
    """Response from pattern test."""

    text: str
    matches: list[PatternTestResult]
    total_patterns_checked: int
    first_match: PatternTestResult | None


class ChangeRecord(BaseModel):
    """Record of a logic change."""

    change_id: str
    logic_type: str
    logic_id: str
    timestamp: str
    user: str
    reason: str
    before_hash: str
    after_hash: str


class OverrideUpdateRequest(BaseModel):
    """Request to update an override."""

    enabled: bool | None = None
    rules: list[dict[str, Any]] | None = None
    reason: str = Field(..., description="Reason for the change")


# =============================================================================
# Helper Functions
# =============================================================================


async def get_registry():
    """Get the LogicRegistry singleton."""
    from barnabeenet.core.logic_registry import get_logic_registry

    return await get_logic_registry()


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=LogicOverviewResponse)
async def get_logic_overview():
    """Get complete overview of all logic (patterns, routing, overrides).

    This is the main endpoint for the Logic Browser dashboard page.
    """
    registry = await get_registry()
    data = registry.to_dict()

    # Transform to response models
    patterns = {}
    for group_name, group_data in data["patterns"].items():
        patterns[group_name] = PatternGroupResponse(
            name=group_data["name"],
            patterns={
                name: PatternDefinitionResponse(**p) for name, p in group_data["patterns"].items()
            },
            pattern_count=len(group_data["patterns"]),
        )

    routing = {name: RoutingRuleResponse(**r) for name, r in data["routing"].items()}

    overrides = {name: OverrideRuleResponse(**o) for name, o in data["overrides"].items()}

    aliases = {name: EntityAliasResponse(**a) for name, a in data["entity_aliases"].items()}

    return LogicOverviewResponse(
        patterns=patterns,
        routing=routing,
        overrides=overrides,
        entity_aliases=aliases,
        stats=data["stats"],
        metadata=data["metadata"],
    )


@router.get("/patterns")
async def list_pattern_groups():
    """List all pattern groups with counts."""
    registry = await get_registry()
    groups = registry.get_all_pattern_groups()

    return {
        "groups": [
            {
                "name": name,
                "pattern_count": len(group.patterns),
                "enabled_count": sum(1 for p in group.patterns.values() if p.enabled),
            }
            for name, group in groups.items()
        ],
        "total_patterns": sum(len(g.patterns) for g in groups.values()),
    }


@router.get("/patterns/{group_name}")
async def get_pattern_group(group_name: str):
    """Get all patterns in a specific group."""
    registry = await get_registry()
    group = registry.get_pattern_group(group_name)

    if not group:
        raise HTTPException(status_code=404, detail=f"Pattern group '{group_name}' not found")

    return {
        "name": group.name,
        "patterns": {
            name: {
                "name": p.name,
                "pattern": p.pattern,
                "sub_category": p.sub_category,
                "confidence": p.confidence,
                "enabled": p.enabled,
                "description": p.description,
                "examples": p.examples,
                "typo_variants": p.typo_variants,
            }
            for name, p in group.patterns.items()
        },
        "pattern_count": len(group.patterns),
    }


@router.get("/patterns/{group_name}/{pattern_name}")
async def get_pattern(group_name: str, pattern_name: str):
    """Get a specific pattern."""
    registry = await get_registry()
    pattern = registry.get_pattern(group_name, pattern_name)

    if not pattern:
        raise HTTPException(
            status_code=404,
            detail=f"Pattern '{pattern_name}' not found in group '{group_name}'",
        )

    return {
        "name": pattern.name,
        "pattern": pattern.pattern,
        "sub_category": pattern.sub_category,
        "confidence": pattern.confidence,
        "enabled": pattern.enabled,
        "description": pattern.description,
        "examples": pattern.examples,
        "typo_variants": pattern.typo_variants,
    }


@router.put("/patterns/{group_name}/{pattern_name}")
async def update_pattern(
    group_name: str,
    pattern_name: str,
    request: PatternUpdateRequest,
):
    """Update a pattern definition."""
    registry = await get_registry()

    # Build updates dict from non-None values
    updates = {}
    if request.pattern is not None:
        # Validate regex
        try:
            re.compile(request.pattern)
        except re.error as e:
            raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}") from e
        updates["pattern"] = request.pattern
    if request.sub_category is not None:
        updates["sub_category"] = request.sub_category
    if request.confidence is not None:
        updates["confidence"] = request.confidence
    if request.enabled is not None:
        updates["enabled"] = request.enabled
    if request.description is not None:
        updates["description"] = request.description
    if request.examples is not None:
        updates["examples"] = request.examples

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    result = await registry.update_pattern(
        group_name=group_name,
        pattern_name=pattern_name,
        updates=updates,
        user="dashboard",  # TODO: Get from auth
        reason=request.reason,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Pattern '{pattern_name}' not found in group '{group_name}'",
        )

    return {
        "success": True,
        "message": f"Pattern '{pattern_name}' updated",
        "pattern": {
            "name": result.name,
            "pattern": result.pattern,
            "sub_category": result.sub_category,
            "confidence": result.confidence,
            "enabled": result.enabled,
        },
    }


@router.post("/patterns/test", response_model=PatternTestResponse)
async def test_patterns(request: PatternTestRequest):
    """Test input text against patterns.

    Returns all matching patterns and which one would be used.
    """
    registry = await get_registry()
    text = request.text.strip()
    groups_to_test = request.groups or [
        "emergency",
        "instant",
        "action",
        "memory",
        "query",
        "gesture",
    ]

    all_matches: list[PatternTestResult] = []
    total_checked = 0

    for group_name in groups_to_test:
        group = registry.get_pattern_group(group_name)
        if not group:
            continue

        for pattern_name, pattern in group.patterns.items():
            total_checked += 1
            matched, match = pattern.matches(text)

            result = PatternTestResult(
                group=group_name,
                pattern_name=pattern_name,
                pattern=pattern.pattern,
                sub_category=pattern.sub_category,
                matched=matched,
                match_groups=list(match.groups()) if match else None,
                confidence=pattern.confidence if matched else 0.0,
            )

            if matched:
                all_matches.append(result)

    # Sort by confidence
    all_matches.sort(key=lambda r: r.confidence, reverse=True)

    return PatternTestResponse(
        text=text,
        matches=all_matches,
        total_patterns_checked=total_checked,
        first_match=all_matches[0] if all_matches else None,
    )


@router.get("/routing")
async def get_routing_rules():
    """Get all routing rules."""
    registry = await get_registry()
    rules = registry.get_all_routing_rules()

    return {
        "rules": {
            name: {
                "intent": r.intent,
                "agent": r.agent,
                "description": r.description,
                "priority": r.priority,
                "requires_llm": r.requires_llm,
                "timeout_ms": r.timeout_ms,
                "enabled": r.enabled,
            }
            for name, r in rules.items()
        },
        "total_rules": len(rules),
    }


@router.get("/routing/{intent}")
async def get_routing_rule(intent: str):
    """Get routing rule for a specific intent."""
    registry = await get_registry()
    rule = registry.get_routing_rule(intent)

    if not rule:
        raise HTTPException(status_code=404, detail=f"Routing rule for '{intent}' not found")

    return {
        "intent": rule.intent,
        "agent": rule.agent,
        "description": rule.description,
        "priority": rule.priority,
        "requires_llm": rule.requires_llm,
        "timeout_ms": rule.timeout_ms,
        "enabled": rule.enabled,
    }


@router.get("/overrides")
async def get_overrides(
    enabled_only: bool = Query(False, description="Only return enabled overrides"),
):
    """Get all override rules."""
    registry = await get_registry()

    if enabled_only:
        overrides = registry.get_enabled_overrides()
        return {
            "overrides": {
                o.name: {
                    "name": o.name,
                    "description": o.description,
                    "enabled": o.enabled,
                    "condition_type": o.condition_type,
                    "conditions": o.conditions,
                    "rules": o.rules,
                }
                for o in overrides
            },
            "total": len(overrides),
        }

    overrides = registry.get_all_overrides()
    return {
        "overrides": {
            name: {
                "name": o.name,
                "description": o.description,
                "enabled": o.enabled,
                "condition_type": o.condition_type,
                "conditions": o.conditions,
                "rules": o.rules,
            }
            for name, o in overrides.items()
        },
        "total": len(overrides),
        "enabled": len(registry.get_enabled_overrides()),
    }


@router.get("/overrides/{override_id}")
async def get_override(override_id: str):
    """Get a specific override rule."""
    registry = await get_registry()
    override = registry.get_override(override_id)

    if not override:
        raise HTTPException(status_code=404, detail=f"Override '{override_id}' not found")

    return {
        "name": override.name,
        "description": override.description,
        "enabled": override.enabled,
        "condition_type": override.condition_type,
        "conditions": override.conditions,
        "rules": override.rules,
    }


@router.put("/overrides/{override_id}")
async def update_override(override_id: str, request: OverrideUpdateRequest):
    """Update an override rule (enable/disable or modify rules)."""
    registry = await get_registry()

    updates = {}
    if request.enabled is not None:
        updates["enabled"] = request.enabled
    if request.rules is not None:
        updates["rules"] = request.rules

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    result = await registry.update_override(
        override_id=override_id,
        updates=updates,
        user="dashboard",
        reason=request.reason,
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"Override '{override_id}' not found")

    return {
        "success": True,
        "message": f"Override '{override_id}' updated",
        "override": {
            "name": result.name,
            "enabled": result.enabled,
        },
    }


@router.get("/aliases")
async def get_entity_aliases():
    """Get all entity aliases."""
    registry = await get_registry()
    aliases = registry.get_all_entity_aliases()

    return {
        "aliases": {
            name: {
                "alias": a.alias,
                "entity_id": a.entity_id,
                "resolve_by": a.resolve_by,
                "domain": a.domain,
                "priority": a.priority,
            }
            for name, a in aliases.items()
        },
        "total": len(aliases),
    }


@router.get("/changes")
async def get_change_history(
    limit: int = Query(50, ge=1, le=200, description="Maximum changes to return"),
):
    """Get recent logic change history."""
    registry = await get_registry()
    changes = registry.get_changes(limit=limit)

    return {
        "changes": changes,
        "total": len(changes),
    }


@router.get("/stats")
async def get_logic_stats():
    """Get logic registry statistics."""
    registry = await get_registry()
    data = registry.to_dict()

    return {
        "stats": data["stats"],
        "metadata": data["metadata"],
    }


@router.get("/decisions")
async def get_recent_decisions(
    limit: int = Query(50, ge=1, le=200, description="Maximum decisions to return"),
):
    """Get recent decision records showing how logic was applied.

    This endpoint shows the history of pattern matches, routing decisions,
    and other logic applications - the "what happened" view of the logic system.
    """
    from barnabeenet.core.decision_registry import get_decision_registry

    registry = get_decision_registry()
    decisions = await registry.get_recent_decisions(limit=limit)

    return {
        "decisions": [d.to_dict() for d in decisions],
        "total": len(decisions),
        "stats": registry.get_stats(),
    }


# =============================================================================
# AI Correction Endpoints
# =============================================================================


class CorrectionAnalyzeRequest(BaseModel):
    """Request to analyze a trace for correction."""

    trace_id: str = Field(..., description="The trace ID to analyze")
    expected_result: str = Field(..., description="What should have happened")
    issue_type: str = Field(..., description="Type of issue reported")


class CorrectionSuggestionResponse(BaseModel):
    """A suggested fix from AI analysis."""

    suggestion_id: str
    suggestion_type: str
    title: str
    description: str
    impact_level: str
    target_logic_id: str
    proposed_value: str | None
    diff_before: str | None
    diff_after: str | None
    confidence: float
    reasoning: str | None


class CorrectionAnalysisResponse(BaseModel):
    """Response from AI correction analysis."""

    analysis_id: str
    trace_id: str
    root_cause: str
    root_cause_logic_id: str | None
    suggestions: list[CorrectionSuggestionResponse]


@router.post("/corrections/analyze", response_model=CorrectionAnalysisResponse)
async def analyze_correction(request: CorrectionAnalyzeRequest):
    """Analyze a trace with AI to diagnose issues and suggest fixes.

    This endpoint:
    1. Loads the full trace with all signals
    2. Gathers the logic configurations that were used
    3. Calls AI to diagnose the root cause
    4. Generates fix suggestions with diff previews
    """
    from barnabeenet.services.ai_correction import get_correction_service

    try:
        correction_service = await get_correction_service()
        analysis = await correction_service.analyze_trace(
            trace_id=request.trace_id,
            expected_result=request.expected_result,
            issue_type=request.issue_type,
        )
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Correction analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}") from None


@router.post("/corrections/{analysis_id}/suggestions/{suggestion_id}/test")
async def test_correction_suggestion(analysis_id: str, suggestion_id: str):
    """Test a suggestion against historical data without applying it.

    Returns metrics on how many traces would be improved vs regressed.
    """
    from barnabeenet.services.ai_correction import get_correction_service

    try:
        correction_service = await get_correction_service()
        results = await correction_service.test_suggestion(
            analysis_id=analysis_id,
            suggestion_id=suggestion_id,
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Suggestion test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}") from None


@router.post("/corrections/{analysis_id}/suggestions/{suggestion_id}/apply")
async def apply_correction_suggestion(analysis_id: str, suggestion_id: str):
    """Apply a suggested fix.

    This modifies the logic configuration (patterns, routing, etc.)
    and marks the original trace as corrected.
    """
    from barnabeenet.services.ai_correction import get_correction_service

    try:
        correction_service = await get_correction_service()
        result = await correction_service.apply_suggestion(
            analysis_id=analysis_id,
            suggestion_id=suggestion_id,
            user="dashboard",
        )
        return {
            "success": True,
            "applied_at": result.applied_at.isoformat() if result.applied_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Apply suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Apply failed: {str(e)}") from None


# =============================================================================
# Diagnostics Endpoints
# =============================================================================


class DiagnoseTextRequest(BaseModel):
    """Request for text diagnosis."""

    text: str = Field(..., description="The text to diagnose")
    include_all_checks: bool = Field(
        False, description="Include all pattern checks, not just near misses"
    )


class DiagnoseTextResponse(BaseModel):
    """Response from text diagnosis."""

    input_text: str
    normalized_text: str
    winner: dict[str, Any] | None
    near_misses: list[dict[str, Any]]
    total_patterns_checked: int
    classification_method: str
    processing_time_ms: float
    suggested_patterns: list[str]
    suggested_modifications: list[dict[str, Any]]


@router.post("/diagnostics/diagnose", response_model=DiagnoseTextResponse)
async def diagnose_text(request: DiagnoseTextRequest):
    """Diagnose why a text input matches or doesn't match patterns.

    This provides detailed analysis including:
    - Which pattern matched (if any)
    - Near-miss patterns that almost matched
    - Why patterns failed (typo, word order, missing keyword, etc.)
    - Suggestions for new patterns or modifications
    """
    from barnabeenet.services.logic_diagnostics import get_diagnostics_service

    registry = await get_registry()
    diagnostics = get_diagnostics_service()

    # Get compiled patterns from registry
    compiled_patterns: dict[str, list[tuple[re.Pattern[str], str]]] = {}
    pattern_priority = [
        ("emergency", "EMERGENCY", 0.99),
        ("instant", "INSTANT", 0.95),
        ("gesture", "GESTURE", 0.95),
        ("action", "ACTION", 0.90),
        ("memory", "MEMORY", 0.90),
        ("query", "QUERY", 0.85),
    ]

    for group_name, _intent, _confidence in pattern_priority:
        group = registry.get_pattern_group(group_name)
        if group:
            patterns = []
            for pattern in group.patterns.values():
                if pattern.enabled:
                    try:
                        compiled = re.compile(pattern.pattern, re.IGNORECASE)
                        patterns.append((compiled, pattern.sub_category))
                    except re.error:
                        pass
            compiled_patterns[group_name] = patterns

    # Run diagnosis
    diag = diagnostics.diagnose_pattern_match(
        text=request.text,
        compiled_patterns=compiled_patterns,
        pattern_priority=pattern_priority,
    )

    return DiagnoseTextResponse(
        input_text=diag.input_text,
        normalized_text=diag.normalized_text,
        winner=diag._check_to_dict(diag.winner) if diag.winner else None,
        near_misses=[diag._check_to_dict(nm) for nm in diag.near_misses[:10]],
        total_patterns_checked=diag.total_patterns_checked,
        classification_method=diag.classification_method,
        processing_time_ms=diag.processing_time_ms,
        suggested_patterns=diag.suggested_patterns[:5],
        suggested_modifications=diag.suggested_modifications[:5],
    )


@router.get("/diagnostics/stats")
async def get_diagnostics_stats():
    """Get diagnostics statistics.

    Returns:
    - Pattern match success rate
    - Common failure reasons
    - Patterns that frequently almost match
    """
    from barnabeenet.services.logic_diagnostics import get_diagnostics_service

    diagnostics = get_diagnostics_service()
    return diagnostics.get_stats()


@router.get("/diagnostics/failures")
async def get_recent_failures(limit: int = Query(50, le=200)):
    """Get recent classification failures.

    Returns cases where no pattern matched, useful for identifying
    gaps in pattern coverage.
    """
    from barnabeenet.services.logic_diagnostics import get_diagnostics_service

    diagnostics = get_diagnostics_service()
    failures = diagnostics.get_recent_failures(limit=limit)

    return {
        "failures": [f.to_dict() for f in failures],
        "total": len(failures),
    }


class FullClassifyRequest(BaseModel):
    """Request for full classification with diagnostics."""

    text: str = Field(..., description="The text to classify")
    speaker: str | None = Field(None, description="Speaker ID if known")
    room: str | None = Field(None, description="Room where request originated")


@router.post("/diagnostics/classify")
async def full_classify_with_diagnostics(request: FullClassifyRequest):
    """Run full MetaAgent classification with detailed diagnostics.

    This calls the actual MetaAgent (pattern → heuristic → LLM fallback)
    and returns all diagnostic information about the classification process.
    """
    from barnabeenet.agents.meta import MetaAgent

    # Create a MetaAgent instance with diagnostics enabled
    meta = MetaAgent(enable_diagnostics=True)
    await meta.init()

    try:
        result = await meta.classify(
            request.text,
            {
                "speaker": request.speaker,
                "room": request.room,
            },
        )

        return {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "sub_category": result.sub_category,
            "target_agent": result.target_agent,
            "priority": result.priority,
            "matched_pattern": result.matched_pattern,
            "classification_method": result.classification_method,
            "patterns_checked": result.patterns_checked,
            "near_miss_patterns": result.near_miss_patterns,
            "failure_diagnosis": result.failure_diagnosis,
            "diagnostics_summary": result.diagnostics_summary,
            "processing_time_ms": result.total_processing_time_ms,
            "context_evaluation": (
                {
                    "emotional_tone": result.context.emotional_tone.value,
                    "urgency_level": result.context.urgency_level.value,
                    "empathy_needed": result.context.empathy_needed,
                }
                if result.context
                else None
            ),
        }
    finally:
        await meta.shutdown()


# =============================================================================
# Health Monitor Endpoints
# =============================================================================


@router.get("/health")
async def get_logic_health_report():
    """Get a comprehensive health report for the logic system.

    This endpoint analyzes the classification history to detect:
    - Inconsistent classifications (same input → different results)
    - Frequent near-misses (patterns that almost match)
    - High failure rates (too many inputs falling to LLM)
    - Confidence drift (decreasing classification confidence)

    Use this to identify areas where patterns need improvement.
    """
    from barnabeenet.services.logic_health import get_health_monitor

    monitor = get_health_monitor()
    report = monitor.generate_health_report()

    return report.to_dict()


@router.get("/health/stats")
async def get_health_stats():
    """Get summary statistics from the health monitor."""
    from barnabeenet.services.logic_health import get_health_monitor

    monitor = get_health_monitor()
    return monitor.get_stats()


@router.get("/health/inconsistent")
async def get_inconsistent_classifications():
    """Get inputs that have been classified inconsistently.

    These are inputs where the same (normalized) text produced
    different classification results over time.
    """
    from barnabeenet.services.logic_health import get_health_monitor

    monitor = get_health_monitor()
    inconsistent = monitor.get_inconsistent_inputs()

    return {
        "inconsistent_inputs": inconsistent,
        "total": len(inconsistent),
    }


@router.get("/health/near-misses")
async def get_frequent_near_misses(
    min_count: int = Query(3, ge=1, description="Minimum near-miss count to include"),
):
    """Get patterns that frequently almost match.

    These are potential gaps in the pattern library - patterns that
    came close to matching but didn't, suggesting the pattern could
    be expanded or a new pattern added.
    """
    from barnabeenet.services.logic_health import get_health_monitor

    monitor = get_health_monitor()
    near_misses = monitor.get_frequent_near_misses(min_count=min_count)

    return {
        "near_misses": near_misses,
        "total": len(near_misses),
    }


@router.post("/health/clear")
async def clear_health_data():
    """Clear all health monitoring data.

    Use this to reset tracking after making pattern changes.
    """
    from barnabeenet.services.logic_health import get_health_monitor

    monitor = get_health_monitor()
    monitor.clear()

    return {"status": "cleared", "message": "Health monitoring data cleared"}
