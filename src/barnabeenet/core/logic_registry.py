"""Logic Registry - Storage and management of editable logic.

All decision logic that can be edited via the dashboard is stored here.
This includes patterns, prompts, thresholds, routing rules, and overrides.

The Logic Registry provides:
1. Loading logic from YAML config files
2. Hot-reload when config changes
3. Version tracking for audit trail
4. API for dashboard editing
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PatternDefinition:
    """A single pattern definition."""

    name: str
    pattern: str
    sub_category: str
    confidence: float = 0.9
    enabled: bool = True
    description: str = ""
    examples: list[str] = field(default_factory=list)
    typo_variants: list[str] = field(default_factory=list)

    # Runtime compiled pattern (not serialized)
    _compiled: re.Pattern | None = field(default=None, repr=False)

    @property
    def compiled(self) -> re.Pattern:
        """Get compiled regex pattern."""
        if self._compiled is None:
            self._compiled = re.compile(self.pattern, re.IGNORECASE)
        return self._compiled

    def matches(self, text: str) -> tuple[bool, re.Match | None]:
        """Check if text matches this pattern."""
        if not self.enabled:
            return False, None
        match = self.compiled.search(text)
        return match is not None, match


@dataclass
class PatternGroup:
    """A group of related patterns (e.g., all instant patterns)."""

    name: str
    patterns: dict[str, PatternDefinition] = field(default_factory=dict)

    def match(self, text: str) -> tuple[PatternDefinition | None, re.Match | None]:
        """Find first matching pattern in group."""
        for pattern in self.patterns.values():
            matched, match = pattern.matches(text)
            if matched:
                return pattern, match
        return None, None

    def match_all(self, text: str) -> list[tuple[PatternDefinition, re.Match]]:
        """Find all matching patterns in group."""
        matches = []
        for pattern in self.patterns.values():
            matched, match = pattern.matches(text)
            if matched and match:
                matches.append((pattern, match))
        return matches


@dataclass
class RoutingRule:
    """A rule for routing intents to agents."""

    intent: str
    agent: str
    description: str = ""
    priority: int = 5
    requires_llm: bool = False
    timeout_ms: int = 5000
    special_handling: str | None = None
    enabled: bool = True


@dataclass
class OverrideRule:
    """An override rule that modifies normal behavior."""

    name: str
    description: str = ""
    enabled: bool = True
    condition_type: str = ""  # "user", "room", "time", "phrase"
    conditions: dict[str, Any] = field(default_factory=dict)
    rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EntityAlias:
    """Alias configuration for an entity."""

    alias: str
    entity_id: str | None = None
    resolve_by: str | None = None  # "current_room", "prefer_attribute"
    prefer_attribute: str | None = None
    domain: str | None = None
    priority: str = "normal"


@dataclass
class LogicChange:
    """Record of a change to logic."""

    change_id: str
    logic_type: str  # "pattern", "routing", "override", "alias"
    logic_id: str
    timestamp: datetime
    user: str
    reason: str
    before_content: Any
    after_content: Any
    before_hash: str
    after_hash: str


class LogicRegistry:
    """Registry for all editable logic in BarnabeeNet.

    This is the source of truth for:
    - Pattern definitions (instant, action, memory, emergency, etc.)
    - Routing rules (intent → agent mapping)
    - Override configurations (user, room, time-based)
    - Entity aliases

    Usage:
        registry = LogicRegistry(config_dir=Path("config"))
        await registry.initialize()

        # Get all instant patterns
        instant_patterns = registry.get_pattern_group("instant")

        # Check if text matches any action pattern
        pattern, match = registry.match_pattern("action", "turn on the light")
    """

    def __init__(
        self,
        config_dir: Path | str = "config",
    ) -> None:
        """Initialize the Logic Registry.

        Args:
            config_dir: Directory containing YAML config files
        """
        self.config_dir = Path(config_dir)

        # Loaded data
        self._pattern_groups: dict[str, PatternGroup] = {}
        self._routing_rules: dict[str, RoutingRule] = {}
        self._overrides: dict[str, OverrideRule] = {}
        self._entity_aliases: dict[str, EntityAlias] = {}
        self._config_metadata: dict[str, Any] = {}

        # Change tracking
        self._changes: list[LogicChange] = []

        # File hashes for hot-reload detection
        self._file_hashes: dict[str, str] = {}

        self._initialized = False

    async def initialize(self) -> None:
        """Load all logic definitions from config files."""
        if self._initialized:
            return

        logger.info("Initializing LogicRegistry from %s", self.config_dir)

        await self._load_patterns()
        await self._load_routing()
        await self._load_overrides()

        self._initialized = True

        total_patterns = sum(len(g.patterns) for g in self._pattern_groups.values())
        logger.info(
            "LogicRegistry initialized: %d pattern groups (%d patterns), "
            "%d routing rules, %d overrides",
            len(self._pattern_groups),
            total_patterns,
            len(self._routing_rules),
            len(self._overrides),
        )

    async def _load_patterns(self) -> None:
        """Load pattern definitions from config/patterns.yaml."""
        patterns_file = self.config_dir / "patterns.yaml"
        if not patterns_file.exists():
            logger.warning("patterns.yaml not found at %s", patterns_file)
            return

        try:
            with open(patterns_file) as f:
                data = yaml.safe_load(f)

            self._file_hashes["patterns"] = self._hash_content(data)
            self._config_metadata["patterns"] = {
                "version": data.get("version", "unknown"),
                "last_modified": data.get("last_modified", "unknown"),
            }

            # Load each pattern group
            for group_name in [
                "emergency",
                "instant",
                "action",
                "query",
                "memory",
                "gesture",
            ]:
                if group_name in data:
                    group = PatternGroup(name=group_name)
                    for pattern_name, pattern_data in data[group_name].items():
                        pattern = PatternDefinition(
                            name=pattern_name,
                            pattern=pattern_data.get("pattern", ""),
                            sub_category=pattern_data.get("sub_category", ""),
                            confidence=pattern_data.get("confidence", 0.9),
                            enabled=pattern_data.get("enabled", True),
                            description=pattern_data.get("description", ""),
                            examples=pattern_data.get("examples", []),
                            typo_variants=pattern_data.get("typo_variants", []),
                        )
                        group.patterns[pattern_name] = pattern
                    self._pattern_groups[group_name] = group
                    logger.debug(
                        "Loaded %d patterns for group '%s'",
                        len(group.patterns),
                        group_name,
                    )

        except Exception as e:
            logger.error("Failed to load patterns.yaml: %s", e)
            raise

    async def _load_routing(self) -> None:
        """Load routing rules from config/routing.yaml."""
        routing_file = self.config_dir / "routing.yaml"
        if not routing_file.exists():
            logger.warning("routing.yaml not found at %s", routing_file)
            return

        try:
            with open(routing_file) as f:
                data = yaml.safe_load(f)

            self._file_hashes["routing"] = self._hash_content(data)
            self._config_metadata["routing"] = {
                "version": data.get("version", "unknown"),
                "last_modified": data.get("last_modified", "unknown"),
            }

            # Load intent routing rules
            if "intent_routing" in data:
                for intent, rule_data in data["intent_routing"].items():
                    rule = RoutingRule(
                        intent=intent,
                        agent=rule_data.get("agent", "interaction"),
                        description=rule_data.get("description", ""),
                        priority=rule_data.get("priority", 5),
                        requires_llm=rule_data.get("requires_llm", False),
                        timeout_ms=rule_data.get("timeout_ms", 5000),
                        special_handling=rule_data.get("special_handling"),
                    )
                    self._routing_rules[intent] = rule

            # Store other routing config
            self._config_metadata["routing_defaults"] = data.get("defaults", {})
            self._config_metadata["confidence_thresholds"] = data.get("confidence_thresholds", {})
            self._config_metadata["memory_retrieval"] = data.get("memory_retrieval", {})
            self._config_metadata["priority_rules"] = data.get("priority_rules", {})

            logger.debug("Loaded %d routing rules", len(self._routing_rules))

        except Exception as e:
            logger.error("Failed to load routing.yaml: %s", e)
            raise

    async def _load_overrides(self) -> None:
        """Load override rules from config/overrides.yaml."""
        overrides_file = self.config_dir / "overrides.yaml"
        if not overrides_file.exists():
            logger.warning("overrides.yaml not found at %s", overrides_file)
            return

        try:
            with open(overrides_file) as f:
                data = yaml.safe_load(f)

            self._file_hashes["overrides"] = self._hash_content(data)
            self._config_metadata["overrides"] = {
                "version": data.get("version", "unknown"),
                "last_modified": data.get("last_modified", "unknown"),
            }

            # Load user overrides
            if "user_overrides" in data:
                for name, override_data in data["user_overrides"].items():
                    override = OverrideRule(
                        name=name,
                        description=override_data.get("description", ""),
                        enabled=override_data.get("enabled", False),
                        condition_type="user",
                        conditions={"users": override_data.get("users", [])},
                        rules=override_data.get("rules", []),
                    )
                    self._overrides[f"user_{name}"] = override

            # Load room overrides
            if "room_overrides" in data:
                for name, override_data in data["room_overrides"].items():
                    override = OverrideRule(
                        name=name,
                        description=override_data.get("description", ""),
                        enabled=override_data.get("enabled", False),
                        condition_type="room",
                        conditions={
                            "rooms": override_data.get("rooms", []),
                            "time_range": override_data.get("time_range"),
                        },
                        rules=override_data.get("rules", []),
                    )
                    self._overrides[f"room_{name}"] = override

            # Load time overrides
            if "time_overrides" in data:
                for name, override_data in data["time_overrides"].items():
                    override = OverrideRule(
                        name=name,
                        description=override_data.get("description", ""),
                        enabled=override_data.get("enabled", False),
                        condition_type="time",
                        conditions={"time_range": override_data.get("time_range")},
                        rules=override_data.get("rules", []),
                    )
                    self._overrides[f"time_{name}"] = override

            # Load entity aliases
            if "entity_aliases" in data:
                aliases_data = data["entity_aliases"]

                # Specific mappings
                if "specific" in aliases_data:
                    for alias_name, alias_data in aliases_data["specific"].items():
                        alias = EntityAlias(
                            alias=alias_name,
                            entity_id=alias_data.get("entity_id"),
                            domain=alias_data.get("domain"),
                            priority=alias_data.get("priority", "normal"),
                        )
                        self._entity_aliases[alias_name.lower()] = alias

                # Generic aliases (resolve by context)
                if "lights" in aliases_data:
                    for alias_name, alias_data in aliases_data["lights"].items():
                        alias = EntityAlias(
                            alias=alias_name,
                            resolve_by=alias_data.get("resolve_by"),
                            prefer_attribute=alias_data.get("prefer_attribute"),
                        )
                        self._entity_aliases[alias_name.lower()] = alias

            # Load phrase overrides
            if "phrase_overrides" in data:
                for name, override_data in data["phrase_overrides"].items():
                    override = OverrideRule(
                        name=name,
                        description=f"Phrase trigger: {override_data.get('phrases', [])}",
                        enabled=override_data.get("enabled", False),
                        condition_type="phrase",
                        conditions={
                            "phrases": override_data.get("phrases", []),
                            "action": override_data.get("action"),
                            "target": override_data.get("target"),
                            "response": override_data.get("response"),
                        },
                        rules=[],
                    )
                    self._overrides[f"phrase_{name}"] = override

            logger.debug(
                "Loaded %d overrides, %d entity aliases",
                len(self._overrides),
                len(self._entity_aliases),
            )

        except Exception as e:
            logger.error("Failed to load overrides.yaml: %s", e)
            raise

    def _hash_content(self, content: Any) -> str:
        """Generate hash of content for version tracking."""
        import json

        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    # =========================================================================
    # Pattern Access Methods
    # =========================================================================

    def get_pattern_group(self, group_name: str) -> PatternGroup | None:
        """Get a pattern group by name."""
        return self._pattern_groups.get(group_name)

    def get_all_pattern_groups(self) -> dict[str, PatternGroup]:
        """Get all pattern groups."""
        return self._pattern_groups.copy()

    def get_pattern(self, group_name: str, pattern_name: str) -> PatternDefinition | None:
        """Get a specific pattern."""
        group = self._pattern_groups.get(group_name)
        if group:
            return group.patterns.get(pattern_name)
        return None

    def match_pattern(
        self, group_name: str, text: str
    ) -> tuple[PatternDefinition | None, re.Match | None]:
        """Match text against a pattern group."""
        group = self._pattern_groups.get(group_name)
        if group:
            return group.match(text)
        return None, None

    def match_all_patterns(
        self, group_name: str, text: str
    ) -> list[tuple[PatternDefinition, re.Match]]:
        """Match text against all patterns in a group."""
        group = self._pattern_groups.get(group_name)
        if group:
            return group.match_all(text)
        return []

    def get_patterns_as_tuples(self, group_name: str) -> list[tuple[str, str]]:
        """Get patterns as (pattern, sub_category) tuples for backward compatibility."""
        group = self._pattern_groups.get(group_name)
        if not group:
            return []
        return [(p.pattern, p.sub_category) for p in group.patterns.values() if p.enabled]

    # =========================================================================
    # Routing Access Methods
    # =========================================================================

    def get_routing_rule(self, intent: str) -> RoutingRule | None:
        """Get routing rule for an intent."""
        return self._routing_rules.get(intent)

    def get_all_routing_rules(self) -> dict[str, RoutingRule]:
        """Get all routing rules."""
        return self._routing_rules.copy()

    def get_agent_for_intent(self, intent: str) -> str:
        """Get the target agent for an intent."""
        rule = self._routing_rules.get(intent)
        if rule:
            return rule.agent
        # Fallback
        return self._config_metadata.get("routing_defaults", {}).get(
            "unknown_intent", "interaction"
        )

    def get_confidence_threshold(self, threshold_name: str) -> float:
        """Get a confidence threshold value."""
        thresholds = self._config_metadata.get("confidence_thresholds", {})
        return thresholds.get(threshold_name, 0.7)

    # =========================================================================
    # Override Access Methods
    # =========================================================================

    def get_override(self, override_id: str) -> OverrideRule | None:
        """Get an override rule by ID."""
        return self._overrides.get(override_id)

    def get_all_overrides(self) -> dict[str, OverrideRule]:
        """Get all override rules."""
        return self._overrides.copy()

    def get_enabled_overrides(self) -> list[OverrideRule]:
        """Get all enabled override rules."""
        return [o for o in self._overrides.values() if o.enabled]

    def get_entity_alias(self, alias: str) -> EntityAlias | None:
        """Get entity alias configuration."""
        return self._entity_aliases.get(alias.lower())

    def get_all_entity_aliases(self) -> dict[str, EntityAlias]:
        """Get all entity aliases."""
        return self._entity_aliases.copy()

    # =========================================================================
    # Update Methods (for dashboard editing)
    # =========================================================================

    async def update_pattern(
        self,
        group_name: str,
        pattern_name: str,
        updates: dict[str, Any],
        user: str,
        reason: str,
    ) -> PatternDefinition | None:
        """Update a pattern definition."""
        group = self._pattern_groups.get(group_name)
        if not group or pattern_name not in group.patterns:
            return None

        pattern = group.patterns[pattern_name]
        before = {
            "pattern": pattern.pattern,
            "sub_category": pattern.sub_category,
            "confidence": pattern.confidence,
            "enabled": pattern.enabled,
            "description": pattern.description,
        }

        # Apply updates
        if "pattern" in updates:
            pattern.pattern = updates["pattern"]
            pattern._compiled = None  # Clear compiled pattern
        if "sub_category" in updates:
            pattern.sub_category = updates["sub_category"]
        if "confidence" in updates:
            pattern.confidence = updates["confidence"]
        if "enabled" in updates:
            pattern.enabled = updates["enabled"]
        if "description" in updates:
            pattern.description = updates["description"]
        if "examples" in updates:
            pattern.examples = updates["examples"]

        after = {
            "pattern": pattern.pattern,
            "sub_category": pattern.sub_category,
            "confidence": pattern.confidence,
            "enabled": pattern.enabled,
            "description": pattern.description,
        }

        # Record change
        change = LogicChange(
            change_id=f"change_{len(self._changes)}",
            logic_type="pattern",
            logic_id=f"{group_name}.{pattern_name}",
            timestamp=datetime.now(UTC),
            user=user,
            reason=reason,
            before_content=before,
            after_content=after,
            before_hash=self._hash_content(before),
            after_hash=self._hash_content(after),
        )
        self._changes.append(change)

        logger.info(
            "Pattern %s.%s updated by %s: %s",
            group_name,
            pattern_name,
            user,
            reason,
        )

        return pattern

    async def update_override(
        self,
        override_id: str,
        updates: dict[str, Any],
        user: str,
        reason: str,
    ) -> OverrideRule | None:
        """Update an override rule."""
        override = self._overrides.get(override_id)
        if not override:
            return None

        before = {
            "enabled": override.enabled,
            "rules": override.rules,
        }

        # Apply updates
        if "enabled" in updates:
            override.enabled = updates["enabled"]
        if "rules" in updates:
            override.rules = updates["rules"]

        after = {
            "enabled": override.enabled,
            "rules": override.rules,
        }

        # Record change
        change = LogicChange(
            change_id=f"change_{len(self._changes)}",
            logic_type="override",
            logic_id=override_id,
            timestamp=datetime.now(UTC),
            user=user,
            reason=reason,
            before_content=before,
            after_content=after,
            before_hash=self._hash_content(before),
            after_hash=self._hash_content(after),
        )
        self._changes.append(change)

        logger.info("Override %s updated by %s: %s", override_id, user, reason)

        return override

    async def save_to_file(self, file_type: str) -> bool:
        """Save current state back to YAML file."""
        # Implementation for persisting changes
        # For now, just log - full persistence TBD
        logger.info("Would save %s to file (not yet implemented)", file_type)
        return True

    # =========================================================================
    # Serialization for API
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry to dict for API responses."""
        return {
            "patterns": {
                group_name: {
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
                }
                for group_name, group in self._pattern_groups.items()
            },
            "routing": {
                name: {
                    "intent": r.intent,
                    "agent": r.agent,
                    "description": r.description,
                    "priority": r.priority,
                    "requires_llm": r.requires_llm,
                    "timeout_ms": r.timeout_ms,
                    "enabled": r.enabled,
                }
                for name, r in self._routing_rules.items()
            },
            "overrides": {
                name: {
                    "name": o.name,
                    "description": o.description,
                    "enabled": o.enabled,
                    "condition_type": o.condition_type,
                    "conditions": o.conditions,
                    "rules": o.rules,
                }
                for name, o in self._overrides.items()
            },
            "entity_aliases": {
                name: {
                    "alias": a.alias,
                    "entity_id": a.entity_id,
                    "resolve_by": a.resolve_by,
                    "domain": a.domain,
                    "priority": a.priority,
                }
                for name, a in self._entity_aliases.items()
            },
            "metadata": self._config_metadata,
            "stats": {
                "total_patterns": sum(len(g.patterns) for g in self._pattern_groups.values()),
                "total_routing_rules": len(self._routing_rules),
                "total_overrides": len(self._overrides),
                "enabled_overrides": len(self.get_enabled_overrides()),
                "total_aliases": len(self._entity_aliases),
                "changes_count": len(self._changes),
            },
        }

    def get_changes(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent changes for audit trail."""
        changes = self._changes[-limit:]
        return [
            {
                "change_id": c.change_id,
                "logic_type": c.logic_type,
                "logic_id": c.logic_id,
                "timestamp": c.timestamp.isoformat(),
                "user": c.user,
                "reason": c.reason,
                "before_hash": c.before_hash,
                "after_hash": c.after_hash,
            }
            for c in reversed(changes)
        ]


# Singleton instance
_logic_registry: LogicRegistry | None = None


async def get_logic_registry(config_dir: Path | str = "config") -> LogicRegistry:
    """Get the singleton LogicRegistry instance."""
    global _logic_registry
    if _logic_registry is None:
        _logic_registry = LogicRegistry(config_dir=config_dir)
        await _logic_registry.initialize()
    return _logic_registry


def reset_logic_registry() -> None:
    """Reset the singleton (for testing)."""
    global _logic_registry
    _logic_registry = None
