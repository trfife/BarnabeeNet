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
