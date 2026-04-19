#!/usr/bin/env python3
"""
Unit tests for external API clients.

Tests embedding and rerank clients.
"""
import sys
import os
sys.path.insert(0, '.')

import numpy as np
from infrastructure.external.embedding_client import EmbeddingClient
from infrastructure.external.rerank_client import RerankClient


def test_embedding_client_init():
    """Test EmbeddingClient initialization."""
    print("Testing EmbeddingClient initialization...")

    # Test with mock API key
    client = EmbeddingClient(
        provider="dashscope",
        api_key="test_key",
        model="text-embedding-v4",
        dimensions=1024
    )

    assert client.provider == "dashscope"
    assert client.model == "text-embedding-v4"
    assert client.dimensions == 1024
    assert client.api_key == "test_key"

    print("✓ EmbeddingClient initialized correctly")


def test_embedding_client_repr():
    """Test EmbeddingClient string representation."""
    print("\nTesting EmbeddingClient __repr__...")

    client = EmbeddingClient(
        provider="dashscope",
        api_key="test_key"
    )

    repr_str = repr(client)
    assert "provider=dashscope" in repr_str
    assert "model=" in repr_str

    print(f"✓ __repr__: {repr_str}")


def test_rerank_client_init():
    """Test RerankClient initialization."""
    print("\nTesting RerankClient initialization...")

    client = RerankClient(
        provider="dashscope",
        api_key="test_key",
        model="qwen3-rerank"
    )

    assert client.provider == "dashscope"
    assert client.model == "qwen3-rerank"
    assert client.api_key == "test_key"

    print("✓ RerankClient initialized correctly")


def test_rerank_client_repr():
    """Test RerankClient string representation."""
    print("\nTesting RerankClient __repr__...")

    client = RerankClient(
        provider="dashscope",
        api_key="test_key"
    )

    repr_str = repr(client)
    assert "provider=dashscope" in repr_str
    assert "model=" in repr_str

    print(f"✓ __repr__: {repr_str}")


def test_embedding_validations():
    """Test embedding input validation."""
    print("\nTesting embedding input validation...")

    client = EmbeddingClient(
        provider="dashscope",
        api_key="test_key"
    )

    # Test empty text
    try:
        client.embed("")
        assert False, "Should raise ValueError for empty text"
    except ValueError as e:
        print(f"✓ Empty text validation: {e}")

    # Test empty batch
    result = client.embed_batch([])
    assert result.shape == (0, 1024)
    print(f"✓ Empty batch returns empty array: shape={result.shape}")

    # Test whitespace-only text
    result = client.embed_batch(["   ", "\n\n", ""])
    assert result.shape == (0, 1024)
    print(f"✓ Whitespace-only texts filtered: shape={result.shape}")


def test_rerank_validations():
    """Test rerank input validation."""
    print("\nTesting rerank input validation...")

    client = RerankClient(
        provider="dashscope",
        api_key="test_key"
    )

    # Test empty query
    try:
        client.rerank("", ["doc1", "doc2"])
        assert False, "Should raise ValueError for empty query"
    except ValueError as e:
        print(f"✓ Empty query validation: {e}")

    # Test empty documents
    result = client.rerank("query", [])
    assert result == []
    print(f"✓ Empty documents returns empty list: {result}")


def test_unsupported_provider():
    """Test unsupported provider error."""
    print("\nTesting unsupported provider...")

    # EmbeddingClient
    try:
        client = EmbeddingClient(provider="unknown")
        assert False, "Should raise ValueError for unknown provider"
    except ValueError as e:
        print(f"✓ EmbeddingClient unknown provider: {e}")

    # RerankClient
    try:
        client = RerankClient(provider="unknown")
        assert False, "Should raise ValueError for unknown provider"
    except ValueError as e:
        print(f"✓ RerankClient unknown provider: {e}")


def test_missing_api_key():
    """Test missing API key handling."""
    print("\nTesting missing API key...")

    # Remove API key from environment temporarily
    original_key = os.environ.get("DASHSCOPE_API_KEY")
    if "DASHSCOPE_API_KEY" in os.environ:
        del os.environ["DASHSCOPE_API_KEY"]

    try:
        # EmbeddingClient
        try:
            client = EmbeddingClient(provider="dashscope", api_key=None)
            assert False, "Should raise ValueError for missing API key"
        except ValueError as e:
            print(f"✓ EmbeddingClient missing API key: {e}")

        # RerankClient
        try:
            client = RerankClient(provider="dashscope", api_key=None)
            assert False, "Should raise ValueError for missing API key"
        except ValueError as e:
            print(f"✓ RerankClient missing API key: {e}")

    finally:
        # Restore original key
        if original_key:
            os.environ["DASHSCOPE_API_KEY"] = original_key


if __name__ == "__main__":
    print("=" * 60)
    print("Unit Tests: External API Clients")
    print("=" * 60)

    try:
        test_embedding_client_init()
        test_embedding_client_repr()
        test_rerank_client_init()
        test_rerank_client_repr()
        test_embedding_validations()
        test_rerank_validations()
        test_unsupported_provider()
        test_missing_api_key()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
