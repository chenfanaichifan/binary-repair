"""Unified LLM gateway for cloud (OpenRouter), local (Ollama) and mock calls."""
from .base import (
    ChatMessage,
    ConfigurationError,
    EmptyContentError,
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    GenerateRequest,
    GenerateResult,
    GenerationRequest,
    GenerationResult,
    HTTPStatusError,
    LLMProvider,
    ModelIdentityError,
    ProviderError,
    ResponseError,
    TimeoutError,
    TransportError,
    annotate_identity,
    model_identity_ok,
)
from .client import DEFAULT_PROVIDER, Gateway, LLMClient, LLMGateway, create_gateway, gateway_from_env
from .providers import (
    MockAdapter,
    MockProvider,
    OllamaAdapter,
    OllamaProvider,
    OpenRouterAdapter,
    OpenRouterProvider,
)

__all__ = [
    "ChatMessage", "GenerationRequest", "GenerationResult", "GatewayRequest",
    "GatewayResponse", "GenerateRequest", "GenerateResult", "LLMGateway",
    "Gateway", "LLMClient", "gateway_from_env", "create_gateway",
    "DEFAULT_PROVIDER", "OpenRouterProvider", "OllamaProvider", "MockProvider",
    "OpenRouterAdapter", "OllamaAdapter", "MockAdapter", "LLMProvider",
    "GatewayError", "ProviderError", "ConfigurationError", "TransportError",
    "TimeoutError", "HTTPStatusError", "ResponseError", "EmptyContentError",
    "ModelIdentityError", "model_identity_ok", "annotate_identity",
]
