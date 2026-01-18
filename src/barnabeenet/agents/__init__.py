"""Agent package for BarnabeeNet.

Contains agent interfaces, simple local agents, and manager.
"""

from .action import ActionAgent, ActionSpec, ActionType, DeviceDomain
from .instant import InstantAgent
from .interaction import (
    BARNABEE_PERSONA,
    ConversationContext,
    ConversationTurn,
    InteractionAgent,
    InteractionConfig,
)
from .manager import AgentManager
from .memory import (
    Event,
    Memory,
    MemoryAgent,
    MemoryConfig,
    MemoryOperation,
    MemoryType,
)
from .meta import (
    ClassificationResult,
    ContextEvaluation,
    EmotionalTone,
    IntentCategory,
    MemoryQuerySet,
    MetaAgent,
    MetaAgentConfig,
    UrgencyLevel,
)

__all__ = [
    "ActionAgent",
    "ActionSpec",
    "ActionType",
    "AgentManager",
    "BARNABEE_PERSONA",
    "ClassificationResult",
    "ContextEvaluation",
    "ConversationContext",
    "ConversationTurn",
    "DeviceDomain",
    "EmotionalTone",
    "Event",
    "InstantAgent",
    "IntentCategory",
    "InteractionAgent",
    "InteractionConfig",
    "Memory",
    "MemoryAgent",
    "MemoryConfig",
    "MemoryOperation",
    "MemoryQuerySet",
    "MemoryType",
    "MetaAgent",
    "MetaAgentConfig",
    "UrgencyLevel",
]
