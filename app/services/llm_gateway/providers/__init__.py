"""Built-in LLM provider adapters."""
from .mock import MockProvider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider

OpenRouterAdapter = OpenRouterProvider
OllamaAdapter = OllamaProvider
MockAdapter = MockProvider

__all__ = [
    "OpenRouterProvider", "OllamaProvider", "MockProvider",
    "OpenRouterAdapter", "OllamaAdapter", "MockAdapter",
]
