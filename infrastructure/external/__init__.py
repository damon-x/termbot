"""
External API clients infrastructure.

Provides unified interfaces for external services:
- EmbeddingClient: Text embedding computation
- RerankClient: Document reranking
"""
from infrastructure.external.embedding_client import (
    EmbeddingClient,
    get_embedding_client,
)
from infrastructure.external.rerank_client import RerankClient, get_rerank_client

__all__ = [
    "EmbeddingClient",
    "get_embedding_client",
    "RerankClient",
    "get_rerank_client",
]
