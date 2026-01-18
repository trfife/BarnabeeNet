"""Agent package for BarnabeeNet.

Contains agent interfaces, simple local agents, manager, and orchestrator.
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
from .orchestrator import (
    AgentOrchestrator,
    OrchestratorConfig,
    RequestContext,
    get_orchestrator,
    process_request,
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
    "OrchestratorConfig",
    "AgentOrchestrator",
    "RequestContext",
    "UrgencyLevel",
    "get_orchestrator",
    "process_request",
]
