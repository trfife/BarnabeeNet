"""LLM Activity definitions and configuration.

Provides granular control over which model/provider is used for each
specific LLM activity across all agents. This allows optimizing for:
- Speed: Use fast models for high-frequency classification
- Cost: Use cheap models for simple tasks
- Quality: Use best models for complex conversations
- Specialization: Use providers best suited for specific tasks

Activities are grouped by agent but can be individually configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LLMActivity(str, Enum):
    """All LLM-requiring activities in BarnabeeNet.

    Organized by agent/service for clarity, but each activity
    can be configured independently.
    """

    # ==========================================================================
    # MetaAgent Activities
    # ==========================================================================
    # Classify user intent (runs on EVERY request - needs to be fast/cheap)
    META_CLASSIFY_INTENT = "meta.classify_intent"
    # Evaluate context/mood (can run in parallel with classification)
    META_EVALUATE_CONTEXT = "meta.evaluate_context"
    # Generate memory search queries
    META_GENERATE_QUERIES = "meta.generate_queries"

    # ==========================================================================
    # ActionAgent Activities
    # ==========================================================================
    # Parse device control intent from natural language
    ACTION_PARSE_INTENT = "action.parse_intent"
    # Resolve entity names to HA entity IDs (when fuzzy matching fails)
    ACTION_RESOLVE_ENTITIES = "action.resolve_entities"
    # Generate confirmation messages
    ACTION_GENERATE_CONFIRM = "action.generate_confirm"
    # Generate error/help messages
    ACTION_GENERATE_ERROR = "action.generate_error"

    # ==========================================================================
    # InteractionAgent Activities
    # ==========================================================================
    # Generate conversational response (quality matters most here)
    INTERACTION_RESPOND = "interaction.respond"
    # Handle follow-up questions in conversation
    INTERACTION_FOLLOWUP = "interaction.followup"
    # Generate empathetic responses (emotional support)
    INTERACTION_EMPATHY = "interaction.empathy"
    # Answer factual questions
    INTERACTION_FACTUAL = "interaction.factual"

    # ==========================================================================
    # MemoryAgent Activities
    # ==========================================================================
    # Generate memories from events/conversations
    MEMORY_GENERATE = "memory.generate"
    # Extract facts from conversation
    MEMORY_EXTRACT_FACTS = "memory.extract_facts"
    # Summarize conversation for storage
    MEMORY_SUMMARIZE = "memory.summarize"
    # Rank/filter retrieved memories for relevance
    MEMORY_RANK = "memory.rank"

    # ==========================================================================
    # Dashboard/API Activities
    # ==========================================================================
    # Generate daily diary summaries from memories
    DIARY_GENERATE = "diary.generate"

    # ==========================================================================
    # Home Assistant Activities
    # ==========================================================================
    # Analyze HA error logs to find important issues
    HA_LOG_ANALYZE = "ha.log_analyze"

    # ==========================================================================
    # Instant Agent (fallback only - usually no LLM)
    # ==========================================================================
    # Fallback for instant patterns that need LLM
    INSTANT_FALLBACK = "instant.fallback"


# Default configurations per activity
# These can be overridden via config/llm.yaml or environment variables
DEFAULT_ACTIVITY_CONFIGS: dict[str, dict[str, Any]] = {
    # MetaAgent - needs to be FAST (runs on every request)
    "meta.classify_intent": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.2,
        "max_tokens": 150,
        "priority": "speed",
        "description": "Intent classification (every request)",
    },
    "meta.evaluate_context": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 100,
        "priority": "speed",
        "description": "Context/mood evaluation",
    },
    "meta.generate_queries": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.4,
        "max_tokens": 200,
        "priority": "speed",
        "description": "Memory query generation",
    },
    # ActionAgent - needs accuracy for device control
    "action.parse_intent": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": 300,
        "priority": "accuracy",
        "description": "Parse device control intent",
    },
    "action.resolve_entities": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 200,
        "priority": "accuracy",
        "description": "Resolve entity names to IDs",
    },
    "action.generate_confirm": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.5,
        "max_tokens": 100,
        "priority": "speed",
        "description": "Generate action confirmations",
    },
    "action.generate_error": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.5,
        "max_tokens": 150,
        "priority": "speed",
        "description": "Generate helpful error messages",
    },
    # InteractionAgent - QUALITY matters (this is the personality)
    "interaction.respond": {
        "model": "anthropic/claude-3.5-sonnet",
        "temperature": 0.7,
        "max_tokens": 1500,
        "priority": "quality",
        "description": "Main conversational responses",
    },
    "interaction.followup": {
        "model": "anthropic/claude-3.5-sonnet",
        "temperature": 0.7,
        "max_tokens": 1000,
        "priority": "quality",
        "description": "Follow-up in conversation",
    },
    "interaction.empathy": {
        "model": "anthropic/claude-3.5-sonnet",
        "temperature": 0.8,
        "max_tokens": 800,
        "priority": "quality",
        "description": "Empathetic/emotional responses",
    },
    "interaction.factual": {
        "model": "openai/gpt-4o",
        "temperature": 0.3,
        "max_tokens": 1000,
        "priority": "accuracy",
        "description": "Factual question answering",
    },
    # MemoryAgent - needs good summarization
    "memory.generate": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 500,
        "priority": "quality",
        "description": "Generate memories from events",
    },
    "memory.extract_facts": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": 400,
        "priority": "accuracy",
        "description": "Extract facts from conversation",
    },
    "memory.summarize": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 300,
        "priority": "quality",
        "description": "Summarize for memory storage",
    },
    "memory.rank": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.2,
        "max_tokens": 100,
        "priority": "speed",
        "description": "Rank memory relevance",
    },
    # Diary/Journal generation
    "diary.generate": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 800,
        "priority": "quality",
        "description": "Generate daily diary summaries from memories",
    },
    # Home Assistant log analysis
    "ha.log_analyze": {
        "model": "openai/gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 1500,
        "priority": "accuracy",
        "description": "Analyze HA logs to identify important issues and patterns",
    },
    # Instant Agent fallback
    "instant.fallback": {
        "model": "deepseek/deepseek-chat",
        "temperature": 0.5,
        "max_tokens": 200,
        "priority": "speed",
        "description": "Fallback for instant patterns",
    },
}


class ActivityConfig(BaseModel):
    """Configuration for a single LLM activity."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: list[str] | None = None

    # Metadata (not sent to LLM)
    priority: str = "balanced"  # speed, cost, quality, accuracy, balanced
    description: str = ""
    provider_override: str | None = None  # Force specific provider


@dataclass
class ActivityConfigManager:
    """Manages LLM activity configurations.

    Loads from:
    1. Built-in defaults (DEFAULT_ACTIVITY_CONFIGS)
    2. YAML config file (config/llm.yaml)
    3. Environment variables (LLM_ACTIVITY_<NAME>_MODEL, etc.)

    Later sources override earlier ones.
    """

    _configs: dict[str, ActivityConfig] = field(default_factory=dict)
    _yaml_path: Path | None = None
    _loaded: bool = False

    def __post_init__(self) -> None:
        """Initialize with default configs."""
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load built-in default configurations."""
        for activity, config_dict in DEFAULT_ACTIVITY_CONFIGS.items():
            self._configs[activity] = ActivityConfig(**config_dict)

    def load_yaml(self, yaml_path: Path | None = None) -> None:
        """Load configuration from YAML file."""
        if yaml_path is None:
            # Try default locations
            possible_paths = [
                Path("config/llm.yaml"),
                Path("/etc/barnabeenet/llm.yaml"),
                Path.home() / ".config/barnabeenet/llm.yaml",
            ]
            for path in possible_paths:
                if path.exists():
                    yaml_path = path
                    break

        if yaml_path is None or not yaml_path.exists():
            logger.debug("No LLM config YAML found, using defaults")
            return

        self._yaml_path = yaml_path

        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)

            # Load activity-specific configs
            activities_data = data.get("activities", {})
            for activity_name, config_dict in activities_data.items():
                if activity_name in self._configs:
                    # Merge with existing config
                    existing = self._configs[activity_name].model_dump()
                    existing.update(config_dict)
                    self._configs[activity_name] = ActivityConfig(**existing)
                else:
                    self._configs[activity_name] = ActivityConfig(**config_dict)

            # Also support legacy agent-level configs (map to primary activity)
            agents_data = data.get("agents", {})
            legacy_mapping = {
                "meta": "meta.classify_intent",
                "instant": "instant.fallback",
                "action": "action.parse_intent",
                "interaction": "interaction.respond",
                "memory": "memory.generate",
            }
            for agent_name, config_dict in agents_data.items():
                if agent_name in legacy_mapping:
                    activity = legacy_mapping[agent_name]
                    if activity in self._configs:
                        existing = self._configs[activity].model_dump()
                        # Only copy model settings, not metadata
                        for key in ["model", "temperature", "max_tokens", "top_p"]:
                            if key in config_dict:
                                existing[key] = config_dict[key]
                        self._configs[activity] = ActivityConfig(**existing)

            logger.info(f"Loaded LLM config from {yaml_path}")

        except Exception as e:
            logger.error(f"Failed to load LLM config from {yaml_path}: {e}")

    def load_env_overrides(self) -> None:
        """Load overrides from environment variables.

        Format: LLM_ACTIVITY_<NAME>_<FIELD>=value
        Example: LLM_ACTIVITY_META_CLASSIFY_INTENT_MODEL=gpt-4o
        """
        import os

        prefix = "LLM_ACTIVITY_"

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # Parse: LLM_ACTIVITY_META_CLASSIFY_INTENT_MODEL -> meta.classify_intent, model
            parts = key[len(prefix) :].lower().split("_")
            if len(parts) < 2:
                continue

            field_name = parts[-1]
            activity_parts = parts[:-1]

            # Convert ACTIVITY_NAME to activity.name
            # META_CLASSIFY_INTENT -> meta.classify_intent
            activity_name = ".".join(
                "_".join(activity_parts[:i]) for i in range(1, len(activity_parts) + 1)
            )

            # Try to find matching activity
            for activity in self._configs:
                env_key = activity.replace(".", "_").upper()
                if "_".join(activity_parts).upper() == env_key:
                    activity_name = activity
                    break

            if activity_name not in self._configs:
                logger.warning(f"Unknown activity in env var {key}: {activity_name}")
                continue

            # Update field
            config = self._configs[activity_name]
            if field_name == "model":
                config.model = value
            elif field_name == "temperature":
                config.temperature = float(value)
            elif field_name == "max_tokens":
                config.max_tokens = int(value)
            elif field_name == "provider":
                config.provider_override = value

            logger.debug(f"Env override: {activity_name}.{field_name} = {value}")

    def get(self, activity: str | LLMActivity) -> ActivityConfig:
        """Get configuration for an activity."""
        if isinstance(activity, LLMActivity):
            activity = activity.value

        if activity in self._configs:
            return self._configs[activity]

        # Try to find by agent prefix for backward compatibility
        agent_prefix = activity.split(".")[0] if "." in activity else activity
        fallback_mapping = {
            "meta": "meta.classify_intent",
            "instant": "instant.fallback",
            "action": "action.parse_intent",
            "interaction": "interaction.respond",
            "memory": "memory.generate",
        }
        if agent_prefix in fallback_mapping:
            return self._configs[fallback_mapping[agent_prefix]]

        # Ultimate fallback
        logger.warning(f"Unknown activity '{activity}', using interaction.respond default")
        return self._configs["interaction.respond"]

    def get_all(self) -> dict[str, ActivityConfig]:
        """Get all activity configurations."""
        return self._configs.copy()

    def list_activities(self) -> list[str]:
        """List all configured activities."""
        return list(self._configs.keys())

    async def load_redis_overrides(self, redis_client: Any) -> None:
        """Load activity config overrides from Redis.

        Should be called during app startup after Redis is initialized.

        Args:
            redis_client: Async Redis client
        """
        import json

        ACTIVITY_CONFIGS_KEY = "barnabeenet:activity_configs"

        try:
            overrides = await redis_client.hgetall(ACTIVITY_CONFIGS_KEY)
            if not overrides:
                logger.debug("No activity config overrides in Redis")
                return

            count = 0
            for activity_name, override_json in overrides.items():
                if activity_name not in self._configs:
                    logger.warning(f"Unknown activity in Redis override: {activity_name}")
                    continue

                override = json.loads(override_json)
                config = self._configs[activity_name]

                if "model" in override:
                    config.model = override["model"]
                if "temperature" in override:
                    config.temperature = override["temperature"]
                if "max_tokens" in override:
                    config.max_tokens = override["max_tokens"]

                count += 1
                logger.debug(f"Redis override: {activity_name} -> {override.get('model')}")

            logger.info(f"Loaded {count} activity config overrides from Redis")
        except Exception as e:
            logger.error(f"Failed to load activity configs from Redis: {e}")


# Global instance
_activity_config_manager: ActivityConfigManager | None = None


def get_activity_config_manager() -> ActivityConfigManager:
    """Get the global activity config manager."""
    global _activity_config_manager
    if _activity_config_manager is None:
        _activity_config_manager = ActivityConfigManager()
        _activity_config_manager.load_yaml()
        _activity_config_manager.load_env_overrides()
    return _activity_config_manager


def get_activity_config(activity: str | LLMActivity) -> ActivityConfig:
    """Convenience function to get config for an activity."""
    return get_activity_config_manager().get(activity)


# Export activity enum members for easy import
__all__ = [
    "LLMActivity",
    "ActivityConfig",
    "ActivityConfigManager",
    "get_activity_config_manager",
    "get_activity_config",
    "DEFAULT_ACTIVITY_CONFIGS",
]
