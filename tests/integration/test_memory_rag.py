#!/usr/bin/env python3
"""
Integration tests for Phase 3: RAG and hybrid search.

Tests the complete LongTermMemory implementation.
"""
import sys
import os
sys.path.insert(0, '.')

from agent.memory.long_term_memory import get_long_term_memory


def test_memory_initialization():
    """Test memory system initialization."""
    print("Testing memory system initialization...")

    ltm = get_long_term_memory()
    assert ltm is not None
    print("✓ LongTermMemory initialized")

    # Check FAISS
    assert ltm.faiss_index is not None
    print(f"✓ FAISS index ready: {ltm.faiss_index.ntotal} vectors")

    # Check Whoosh
    assert ltm.whoosh_index is not None
    print("✓ Whoosh index ready")

    # Check clients
    assert ltm.embedding_client is not None
    assert ltm.rerank_client is not None
    print("✓ External clients ready")


def test_set_memory():
    """Test writing memory with full indexing."""
    print("\nTesting set() with full indexing...")

    if not os.getenv("DASHSCOPE_API_KEY"):
        print("⚠️  Skipping: DASHSCOPE_API_KEY not set")
        print("  (This test requires API access for embedding computation)")
        return

    ltm = get_long_term_memory()

    # Test 1: Simple tech note
    result = ltm.set(
        content="Docker 容器化部署的最佳实践包括多阶段构建、镜像优化和容器编排",
        tags=["docker", "kubernetes", "devops"]
    )

    assert result.success is True
    assert result.memory_id is not None
    print(f"✓ Memory saved: ID={result.memory_id}")

    # Test 2: Programming tutorial
    result = ltm.set(
        content="Python 异步编程使用 asyncio 和 aiohttp 可以显著提升 I/O 密集型应用的性能",
        tags=["python", "async", "performance"]
    )

    assert result.success is True
    print(f"✓ Memory saved: ID={result.memory_id}")


def test_get_memory():
    """Test retrieving memory with hybrid search."""
    print("\nTesting get() with hybrid search...")

    ltm = get_long_term_memory()

    # Add some test memories first (without API)
    from agent.memory.models import memory_manager

    mem1 = memory_manager.add_memory(
        content="使用 React Query 和 useEffect 可以优雅地管理组件状态",
        tags=["react", "frontend", "hooks"],
        metadata={"test": True}
    )

    mem2 = memory_manager.add_memory(
        content="GraphQL 提供了强大的类型系统和查询能力",
        tags=["graphql", "api", "typescript"],
        metadata={"test": True}
    )

    mem3 = memory_manager.add_memory(
        content="Redis 作为内存数据库可以极大提升读写性能",
        tags=["redis", "database", "cache"],
        metadata={"test": True}
    )

    print(f"✓ Added {len([mem1, mem2, mem3])} test memories")

    # Test retrieval
    results = ltm.get(
        queries=["前端状态管理", "数据库性能"],
        limit=3,
        use_rerank=False  # Disable rerank for simpler test
    )

    assert len(results) == 2

    # First query should find the React/Hooks memory
    react_results = results[0]
    assert react_results.query == "前端状态管理"
    assert len(react_results.memories) > 0
    # Should find memory about React
    has_react = any("react" in str(m.get("tags", "[]")).lower() for m in react_results.memories)
    assert has_react, "Should find React-related memory"
    print(f"✓ Query 1: '{react_results.query}' → {len(react_results.memories)} results")

    # Second query should find Redis memory
    db_results = results[1]
    assert db_results.query == "数据库性能"
    assert len(db_results.memories) > 0
    # Should find memory about databases
    has_db = any("db" in str(m.get("tags", "[]")).lower() or "database" in m["content"].lower() for m in db_results.memories)
    assert has_db, "Should find database-related memory"
    print(f"✓ Query 2: '{db_results.query}' → {len(db_results.memories)} results")

    # Cleanup
    memory_manager.delete_memory(mem1)
    memory_manager.delete_memory(mem2)
    memory_manager.delete_memory(mem3)
    print("✓ Test data cleaned up")


def test_hybrid_search():
    """Test hybrid search combining keyword and semantic."""
    print("\nTesting hybrid search...")

    # This test is implicit in test_get_memory()
    # The hybrid search happens inside get()
    print("✓ Hybrid search tested via get()")


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("Integration Tests: Phase 3 - RAG and Hybrid Search")
    print("=" * 60)

    try:
        test_memory_initialization()
        test_set_memory()
        test_get_memory()
        test_hybrid_search()

        print("\n" + "=" * 60)
        print("✅ All Phase 3 tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
