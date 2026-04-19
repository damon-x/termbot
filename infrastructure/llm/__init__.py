"""
LLM client module.

Provides unified API clients for chat and embeddings with multiple
provider support (OpenAI-compatible and Anthropic).
"""
from typing import Union

from infrastructure.config.settings import settings
from infrastructure.llm.openai_client import (
    OpenAIClient,
    EmbeddingClient,
)
from infrastructure.llm.anthropic_client import AnthropicClient
from infrastructure.llm.function_calling import (
    ChatResponse,
    FunctionCall,
    parse_function_call,
)


def get_client(
    provider: str = None,
    model: str = None
) -> Union[OpenAIClient, AnthropicClient]:
    """
    Get LLM client based on configuration.

    Args:
        provider: LLM provider ('openai', 'anthropic', or None to use config)
        model: Model name (optional, overrides config)

    Returns:
        LLM client instance (OpenAIClient or AnthropicClient)
    """
    if provider is None:
        provider = settings.llm.get("provider", "openai")

    if provider == "anthropic":
        return AnthropicClient(model=model)
    else:
        # Default to OpenAI-compatible client
        return OpenAIClient(model=model)


# Default client instances (determined by config)
default_client = get_client()
embedding_client = EmbeddingClient()

# Fast client always uses OpenAI (Qwen Flash)
fast_client = OpenAIClient(model="qwen-flash")

__all__ = [
    "OpenAIClient",
    "AnthropicClient",
    "EmbeddingClient",
    "ChatResponse",
    "FunctionCall",
    "parse_function_call",
    "get_client",
    "default_client",
    "embedding_client",
    "fast_client",
]
