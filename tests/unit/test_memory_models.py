#!/usr/bin/env python3
"""
Unit tests for memory models and LongTermMemory framework.

Tests Phase 2 implementation.
"""
import sys
import os
sys.path.insert(0, '.')

from agent.memory.models import MemoryItem, MemoryManager, memory_manager
from agent.memory.long_term_memory import (
    LongTermMemory,
    MemoryResult,
    SetResult,
    get_long_term_memory,
)


def test_memory_manager_init():
    """Test MemoryManager initialization."""
    print("Testing MemoryManager initialization...")

    manager = memory_manager
    assert manager is not None
    assert manager.engine is not None

    print("✓ MemoryManager initialized correctly")


def test_add_memory():
    """Test adding memory to SQLite."""
    print("\nTesting add_memory()...")

    content = "测试记忆内容：Docker 容器配置"
    tags = ["docker", "配置", "dev"]
    metadata = {"source": "test"}

    memory_id = memory_manager.add_memory(
        content=content,
        tags=tags,
        metadata=metadata
    )

    assert memory_id > 0
    print(f"✓ Memory added with ID: {memory_id}")

    # 验证可以取回
    item = memory_manager.get_memory(memory_id)
    assert item is not None
    assert item.content == content
    assert "docker" in json.loads(item.tags)
    print(f"✓ Memory retrieved successfully")

    return memory_id


def test_get_all_memories():
    """Test getting all memories."""
    print("\nTesting get_all_memories()...")

    memories = memory_manager.get_all_memories(enabled_only=False)
    assert len(memories) > 0
    print(f"✓ Retrieved {len(memories)} memories")


def test_update_access():
    """Test updating access statistics."""
    print("\nTesting update_access()...")

    memories = memory_manager.get_all_memories(limit=1)
    if memories:
        item = memories[0]
        old_count = item.access_count

        memory_manager.update_access(item.id)

        updated = memory_manager.get_memory(item.id)
        assert updated.access_count == old_count + 1
        print(f"✓ Access count updated: {old_count} → {updated.access_count}")


def test_long_term_memory_init():
    """Test LongTermMemory initialization."""
    print("\nTesting LongTermMemory initialization...")

    ltm = get_long_term_memory()
    assert ltm is not None
    assert ltm.memory_manager is not None
    assert ltm.embedding_client is not None
    assert ltm.rerank_client is not None
    assert ltm.whoosh_index is not None

    print("✓ LongTermMemory initialized correctly")


def test_set_result():
    """Test SetResult data structure."""
    print("\nTesting SetResult...")

    result = SetResult(
        success=True,
        memory_id=123,
        message="Test success"
    )

    assert result.success is True
    assert result.memory_id == 123
    assert result.message == "Test success"
    print(f"✓ SetResult: {result}")


def test_memory_result():
    """Test MemoryResult data structure."""
    print("\nTesting MemoryResult...")

    memories = [
        {"id": 1, "content": "Test 1"},
        {"id": 2, "content": "Test 2"}
    ]

    result = MemoryResult(
        query="test query",
        memories=memories,
        retrieval_time=0.5
    )

    assert result.query == "test query"
    assert len(result.memories) == 2
    assert result.retrieval_time == 0.5
    print(f"✓ MemoryResult: {result}")


def test_long_term_memory_set():
    """Test LongTermMemory.set() framework."""
    print("\nTesting LongTermMemory.set()...")

    # 检查是否有 API key
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("⚠️  Skipping: DASHSCOPE_API_KEY not set")
        print("  (This test requires API access for embedding computation)")
        return

    ltm = get_long_term_memory()

    result = ltm.set(
        content="这是一条测试记忆：如何使用 FAISS 向量数据库",
        tags=["faiss", "vector", "database"]
    )

    assert result.success is True
    assert result.memory_id is not None
    assert "成功" in result.message
    print(f"✓ set() returned: {result.message}")


def test_long_term_memory_get():
    """Test LongTermMemory.get() framework."""
    print("\nTesting LongTermMemory.get()...")

    ltm = get_long_term_memory()

    # 先添加一些测试数据（通过 SQLite 直接添加，不需要 API）
    mem_id_1 = memory_manager.add_memory(
        content="Python 异步编程教程",
        tags=["python", "async"],
        metadata={"test": True}
    )

    mem_id_2 = memory_manager.add_memory(
        content="Docker 网络配置",
        tags=["docker", "network"],
        metadata={"test": True}
    )

    # 测试检索（不使用嵌入，只做简单的关键词匹配）
    results = ltm.get(queries=["python", "docker"], limit=5)

    assert len(results) == 2
    assert results[0].query == "python"
    assert results[1].query == "docker"

    for result in results:
        assert isinstance(result, MemoryResult)
        assert isinstance(result.memories, list)
        print(f"  Query '{result.query}' → {len(result.memories)} results")

    # 清理测试数据
    memory_manager.delete_memory(mem_id_1)
    memory_manager.delete_memory(mem_id_2)

    print("✓ get() returned structured results")


def test_memory_item_to_dict():
    """Test MemoryItem.to_dict() conversion."""
    print("\nTesting MemoryItem.to_dict()...")

    memories = memory_manager.get_all_memories(limit=1)
    if memories:
        item = memories[0]
        item_dict = item.to_dict()

        assert "id" in item_dict
        assert "content" in item_dict
        assert "tags" in item_dict
        assert isinstance(item_dict["tags"], list)
        print(f"✓ MemoryItem converted to dict: keys={list(item_dict.keys())}")


def cleanup_test_data():
    """Clean up test data."""
    print("\nCleaning up test data...")

    memories = memory_manager.get_all_memories(enabled_only=False)
    for item in memories:
        # 只删除测试创建的数据
        if "test" in item.metadata or "测试" in item.content:
            memory_manager.delete_memory(item.id)

    print("✓ Test data cleaned up")


def test_list_memories_pagination():
    """Test list_memories with pagination."""
    print("\nTesting list_memories() with pagination...")

    # 添加测试数据
    test_ids = []
    for i in range(10):
        mem_id = memory_manager.add_memory(
            content=f"分页测试笔记 {i}",
            tags=["test", "pagination"],
            metadata={"test": "pagination"}
        )
        test_ids.append(mem_id)

    try:
        # 第一页
        memories, total = memory_manager.list_memories(
            offset=0,
            limit=5,
            sort_by="created_at",
            sort_order="desc"
        )
        assert total >= 10, f"Expected at least 10 memories, got {total}"
        assert len(memories) == 5, f"Expected 5 memories on page 1, got {len(memories)}"
        print(f"✓ Page 1: {len(memories)} memories, total={total}")

        # 第二页
        memories, total = memory_manager.list_memories(
            offset=5,
            limit=5,
            sort_by="created_at",
            sort_order="desc"
        )
        assert len(memories) == 5, f"Expected 5 memories on page 2, got {len(memories)}"
        print(f"✓ Page 2: {len(memories)} memories")

        # 排序测试
        memories_asc, _ = memory_manager.list_memories(
            limit=3,
            sort_by="created_at",
            sort_order="asc"
        )
        memories_desc, _ = memory_manager.list_memories(
            limit=3,
            sort_by="created_at",
            sort_order="desc"
        )
        assert memories_asc[0].id != memories_desc[0].id, "Sort order should be different"
        print(f"✓ Sort order: ASC and DESC work correctly")

    finally:
        # 清理测试数据
        for mem_id in test_ids:
            memory_manager.delete_memory(mem_id)


def test_list_memories_filtering():
    """Test list_memories with tag and search filters."""
    print("\nTesting list_memories() with filtering...")

    # 添加不同类型的测试数据
    docker_id = memory_manager.add_memory(
        content="Docker 容器重启命令",
        tags=["docker", "command"],
        metadata={"test": "filter"}
    )
    python_id = memory_manager.add_memory(
        content="Python 异步编程教程",
        tags=["python", "tutorial"],
        metadata={"test": "filter"}
    )

    try:
        # 标签筛选
        memories, total = memory_manager.list_memories(tag_filter="docker")
        assert total >= 1, f"Expected at least 1 docker memory, got {total}"
        assert any("docker" in m.tags for m in memories), "Should find docker tagged memory"
        print(f"✓ Tag filter 'docker': found {total} memories")

        # 搜索筛选
        memories, total = memory_manager.list_memories(search_query="Python")
        assert total >= 1, f"Expected at least 1 python memory, got {total}"
        assert any("Python" in m.content for m in memories), "Should find Python in content"
        print(f"✓ Search filter 'Python': found {total} memories")

        # 组合筛选
        memories, total = memory_manager.list_memories(
            tag_filter="docker",
            search_query="容器"
        )
        print(f"✓ Combined filter: found {total} memories")

    finally:
        # 清理测试数据
        memory_manager.delete_memory(docker_id)
        memory_manager.delete_memory(python_id)


def test_update_memory():
    """Test update_memory method."""
    print("\nTesting update_memory()...")

    # 添加测试笔记
    mem_id = memory_manager.add_memory(
        content="原始内容：测试笔记",
        tags=["test", "original"],
        metadata={"test": "update"}
    )

    try:
        # 更新内容
        success = memory_manager.update_memory(
            mem_id,
            content="修改后的内容：测试笔记已更新"
        )
        assert success is True, "Update should succeed"
        print(f"✓ Content updated for memory {mem_id}")

        # 验证更新
        updated = memory_manager.get_memory(mem_id)
        assert "修改后" in updated.content, "Content should be updated"
        assert updated.updated_at is not None, "updated_at should be set"
        print(f"✓ Content verified: {updated.content[:20]}...")

        # 更新标签
        success = memory_manager.update_memory(
            mem_id,
            tags=["test", "updated"]
        )
        assert success is True, "Tag update should succeed"
        print(f"✓ Tags updated for memory {mem_id}")

        # 验证标签更新
        updated = memory_manager.get_memory(mem_id)
        import json
        tags = json.loads(updated.tags)
        assert "updated" in tags, "New tag should be present"
        assert "original" not in tags, "Old tag should be removed"
        print(f"✓ Tags verified: {tags}")

        # 同时更新内容和标签
        success = memory_manager.update_memory(
            mem_id,
            content="最终版本内容",
            tags=["test", "final"]
        )
        assert success is True, "Combined update should succeed"
        print(f"✓ Combined update successful")

        # 测试更新不存在的笔记
        success = memory_manager.update_memory(99999, content="test")
        assert success is False, "Update non-existent memory should fail"
        print(f"✓ Non-existent memory update fails correctly")

        # 测试不提供任何更新
        success = memory_manager.update_memory(mem_id)
        # 不提供参数时，仍然应该成功（只是什么都不更新）
        print(f"✓ Empty update handled")

    finally:
        # 清理测试数据
        memory_manager.delete_memory(mem_id)


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("Unit Tests: Memory Models and LongTermMemory")
    print("=" * 60)

    try:
        test_memory_manager_init()
        test_add_memory()
        test_get_all_memories()
        test_update_access()
        test_list_memories_pagination()
        test_list_memories_filtering()
        test_update_memory()
        test_long_term_memory_init()
        test_set_result()
        test_memory_result()
        test_long_term_memory_set()
        test_long_term_memory_get()
        test_memory_item_to_dict()

        print("\n" + "=" * 60)
        print("✅ All Phase 1 & 2 framework tests passed!")
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
    finally:
        cleanup_test_data()
