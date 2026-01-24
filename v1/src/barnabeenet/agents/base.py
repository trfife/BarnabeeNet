from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Agent(ABC):
    """Abstract base class for agents.

    Agents implement `handle_input` to convert text+context into an action
    or response dict. Keep the interface small for easy mocking and testing.
    """

    name: str

    @abstractmethod
    async def init(self) -> None:
        """Optional async initialization (models, clients)."""

    @abstractmethod
    async def handle_input(self, text: str, context: dict | None = None) -> dict[str, Any]:
        """Handle input text and return a response dictionary."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""


__all__ = ["Agent"]
