"""
Backward compatibility module.

This module re-exports from infrastructure.llm to maintain compatibility
with existing imports. New code should use infrastructure.llm directly.
"""
from infrastructure.llm import (
    OpenAIClient,
    EmbeddingClient,
    default_client,
    embedding_client,
    fast_client,
)

# Re-export for backward compatibility
__all__ = [
    "OpenAIClient",
    "EmbeddingClient",
    "default_client",
    "embedding_client",
    "fast_client",
]
