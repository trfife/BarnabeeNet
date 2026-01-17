from __future__ import annotations

import logging

from barnabeenet.agents.base import Agent
from barnabeenet.agents.echo import EchoAgent

logger = logging.getLogger(__name__)


class AgentManager:
    """Registry and runtime helper for agents.

    Keeps a small mapping of agent name -> Agent instance and exposes a
    single `handle` method used by higher-level services.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    async def register_default_agents(self) -> None:
        """Register and initialize default local agents."""
        echo = EchoAgent()
        await echo.init()
        self._agents[echo.name] = echo

    def get(self, name: str) -> Agent | None:
        return self._agents.get(name)

    async def handle(
        self, text: str, agent: str | None = None, context: dict | None = None
    ) -> dict:
        """Dispatch text to the chosen agent (or default EchoAgent).

        Returns the agent's response dict.
        """
        if agent is None:
            # use the first registered agent as default
            agent_obj = next(iter(self._agents.values())) if self._agents else None
        else:
            agent_obj = self._agents.get(agent)

        if agent_obj is None:
            logger.warning("No agent available, falling back to echo")
            agent_obj = EchoAgent()
            await agent_obj.init()

        return await agent_obj.handle_input(text, context=context)


_global_manager: AgentManager | None = None


def get_global_agent_manager() -> AgentManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = AgentManager()
    return _global_manager


__all__ = ["AgentManager", "get_global_agent_manager"]
