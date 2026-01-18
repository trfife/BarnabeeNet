"""LLM services for BarnabeeNet.

Provides OpenRouter client with full signal logging for dashboard observability.
"""

from barnabeenet.services.llm.openrouter import OpenRouterClient
from barnabeenet.services.llm.signals import LLMSignal, SignalLogger

__all__ = ["OpenRouterClient", "LLMSignal", "SignalLogger"]
