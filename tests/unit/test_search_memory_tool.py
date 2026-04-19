#!/usr/bin/env python3
"""Unit tests for SearchMemoryTool - end-to-end test with real database."""
import sys
import os
sys.path.insert(0, '.')

from unittest.mock import patch
from agent.tools.impl import SearchMemoryTool
from agent.memory.models import memory_manager
from agent.memory.long_term_memory import get_long_term_memory, MemoryResult
import json


def test_search_memory_e2e():
    """
    End-to-end test: add memory then search for it.
    Uses SQLite + Whoosh (keyword search), no embedding API needed.
    """
    print("\nTesting: add to SQLite, index to Whoosh, then search")

    search_tool = SearchMemoryTool()
    ltm = get_long_term_memory()

    # Test data
    test_memories = [
        {"content": "Docker bridge network config", "tags": ["docker", "network"]},
        {"content": "Python asyncio best practices", "tags": ["python", "async"]},
        {"content": "FAISS vector database guide", "tags": ["faiss", "vector"]},
    ]

    # 1. Add to SQLite and index to Whoosh
    added_ids = []
    for mem in test_memories:
        mem_id = memory_manager.add_memory(
            content=mem["content"],
            tags=mem["tags"],
            metadata={"test": True}
        )
        added_ids.append(mem_id)
        ltm._index_to_whoosh(mem_id, mem["content"])
        print(f"  + Added ID {mem_id}: {mem['tags'][0]}")

    print(f"  Total: {len(added_ids)} memories added")

    # 2. Mock get() to use only Whoosh (skip FAISS/embedding)
    def mock_get(queries, limit=5, use_rerank=False):
        """Mock that uses real Whoosh search, skips FAISS."""
        results = []
        for query in queries:
            scores = ltm._search_whoosh(query)
            top_ids = sorted(scores.items(), key=lambda x: -x[1])[:limit]

            memories = []
            for mem_id, score in top_ids:
                item = memory_manager.get_memory(mem_id)
                if item is not None and item.enabled:
                    memories.append({
                        "id": item.id,
                        "content": item.content,
                        "tags": json.loads(item.tags) if item.tags else [],
                        "score": score,
                    })
                    memory_manager.update_access(mem_id)

            results.append(MemoryResult(
                query=query,
                memories=memories,
                retrieval_time=0.1
            ))
        return results

    # 3. Test search with mocked get()
    with patch.object(ltm, 'get', side_effect=mock_get):
        # Test single query
        result = search_tool.execute(queries=["docker"])
        assert "Query: docker" in result
        assert "docker" in result.lower()
        print("  + Single query works")

        # Test multiple queries
        result = search_tool.execute(queries=["docker", "python"])
        assert "Query: docker" in result
        assert "Query: python" in result
        print("  + Multiple queries work")

        # Test empty result
        result = search_tool.execute(queries=["xyz123nonexistent"])
        assert "No results found" in result
        print("  + Empty result handled")

    # 4. Cleanup
    for mem_id in added_ids:
        memory_manager.delete_memory(mem_id)
    print(f"  Cleaned up {len(added_ids)} test memories")

    print("  PASS: end-to-end test\n")


if __name__ == "__main__":
    print("=" * 60)
    print("SearchMemoryTool: End-to-End Test")
    print("=" * 60)

    try:
        test_search_memory_e2e()
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
