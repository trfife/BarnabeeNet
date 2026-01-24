from __future__ import annotations

from typing import Any

from barnabeenet.agents.base import Agent


class EchoAgent(Agent):
    """Simple agent that echoes input back.

    Useful as a local placeholder and for unit tests.
    """

    name = "echo"

    async def init(self) -> None:
        return None

    async def handle_input(self, text: str, context: dict | None = None) -> dict[str, Any]:
        return {"response": f"You said: {text}", "intent": "echo"}

    async def shutdown(self) -> None:
        return None


__all__ = ["EchoAgent"]
