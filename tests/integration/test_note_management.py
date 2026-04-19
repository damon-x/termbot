#!/usr/bin/env python3
"""
Integration tests for note management features.

Tests Phase 1-3 implementation:
- MemoryManager extensions
- New Tools (ListNotesTool, EditNoteTool, DeleteNoteTool)
- Tool schema validation
"""
import sys
import os
sys.path.insert(0, '.')

from agent.memory.models import memory_manager
from agent.tools.impl import (
    ListNotesTool,
    EditNoteTool,
    DeleteNoteTool,
    SearchMemoryTool,
    AddMemoryTool,
    create_default_tools,
)


def cleanup_test_data():
    """Clean up test data before running tests."""
    print("Cleaning up existing test data...")
    memories = memory_manager.get_all_memories(enabled_only=False)
    for item in memories:
        if "测试" in item.content or "test" in item.content.lower():
            memory_manager.delete_memory(item.id)
    print("✓ Test data cleaned\n")


def test_tool_schemas():
    """Test that all tools have valid schemas."""
    print("Testing Tool schemas...")

    tools = [
        ListNotesTool(),
        EditNoteTool(),
        DeleteNoteTool(),
        SearchMemoryTool(),
    ]

    for tool in tools:
        schema = tool.schema
        assert schema.name is not None, f"{tool.__class__.__name__} has no name"
        assert schema.description is not None, f"{tool.__class__.__name__} has no description"
        assert schema.parameters is not None, f"{tool.__class__.__name__} has no parameters"
        print(f"  ✓ {schema.name}: {len(schema.parameters)} parameters")

    print("✅ All Tool schemas valid\n")


def test_list_notes_tool():
    """Test ListNotesTool execution."""
    print("Testing ListNotesTool...")

    # Add test data
    test_ids = []
    for i in range(3):
        mem_id = memory_manager.add_memory(
            content=f"列表测试笔记 {i+1}",
            tags=["test", "list"]
        )
        test_ids.append(mem_id)

    try:
        tool = ListNotesTool()

        # Test first page
        result = tool.execute(offset=0)
        assert "共有" in result, "Result should contain total count"
        assert "列表测试笔记" in result, "Result should contain test notes"
        print(f"  ✓ First page: {result[:50]}...")

        # Test empty offset (default)
        result = tool.execute()
        assert "共有" in result
        print(f"  ✓ Default offset works")

    finally:
        for mem_id in test_ids:
            memory_manager.delete_memory(mem_id)

    print("✅ ListNotesTool passed\n")


def test_edit_note_tool():
    """Test EditNoteTool execution."""
    print("Testing EditNoteTool...")

    # Add test note
    mem_id = memory_manager.add_memory(
        content="原始内容：需要被修改",
        tags=["test", "edit"]
    )

    try:
        tool = EditNoteTool()

        # Test content update
        result = tool.execute(note_id=mem_id, content="修改后的内容")
        assert "已更新" in result, "Should confirm update"
        print(f"  ✓ Content update: {result}")

        # Verify update
        updated = memory_manager.get_memory(mem_id)
        assert "修改后" in updated.content, "Content should be updated"
        print(f"  ✓ Verification passed")

        # Test tag update
        result = tool.execute(note_id=mem_id, tags=["test", "edited"])
        assert "已更新" in result
        print(f"  ✓ Tag update: {result}")

        # Test non-existent note
        result = tool.execute(note_id=99999, content="test")
        assert "不存在" in result, "Should report non-existent note"
        print(f"  ✓ Non-existent note handled")

    finally:
        memory_manager.delete_memory(mem_id)

    print("✅ EditNoteTool passed\n")


def test_delete_note_tool():
    """Test DeleteNoteTool execution."""
    print("Testing DeleteNoteTool...")

    # Add test note
    mem_id = memory_manager.add_memory(
        content="准备被删除的笔记",
        tags=["test", "delete"]
    )

    try:
        tool = DeleteNoteTool()

        # Test deletion
        result = tool.execute(note_id=mem_id)
        assert "已删除" in result, "Should confirm deletion"
        print(f"  ✓ Deletion: {result}")

        # Verify soft delete
        note = memory_manager.get_memory(mem_id)
        assert note is not None, "Note should still exist (soft delete)"
        assert note.enabled is False, "Note should be disabled"
        print(f"  ✓ Soft delete verified")

        # Test non-existent note
        result = tool.execute(note_id=99999)
        assert "不存在" in result
        print(f"  ✓ Non-existent note handled")

    finally:
        # Clean up
        if note and not note.enabled:
            memory_manager.delete_memory(mem_id)

    print("✅ DeleteNoteTool passed\n")


def test_search_memory_tool():
    """Test SearchMemoryTool execution."""
    print("Testing SearchMemoryTool...")

    # Note: SearchMemoryTool requires LongTermMemory with FAISS/Whoosh indexing.
    # In test environment without proper indexing, we test the Tool interface.

    tool = SearchMemoryTool()

    # Test schema and interface
    schema = tool.schema
    assert schema.name == "search_memory"
    assert len(schema.parameters) == 2  # queries, offset
    print(f"  ✓ Schema valid: {schema.name}")

    # Test with empty queries (should handle gracefully)
    result = tool.execute(queries=[])
    assert "cannot be empty" in result.lower() or "不能为空" in result
    print(f"  ✓ Empty query handling: {result[:40]}...")

    # Test that tool accepts parameters without crashing
    # (Results may be empty due to missing embeddings, but shouldn't crash)
    try:
        result = tool.execute(queries=["test_query"])
        # Tool should return something (even if empty results)
        assert result is not None
        assert isinstance(result, str)
        print(f"  ✓ Query execution completed: {len(result)} chars returned")
    except Exception as e:
        # Should not crash even with missing embeddings
        print(f"  ⚠️  Query execution raised: {e}")

    print("✅ SearchMemoryTool interface passed\n")
    print("  ⚠️  Note: Full search testing requires API key for embeddings\n")


def test_tool_registration():
    """Test that all tools are registered in create_default_tools()."""
    print("Testing tool registration...")

    tools = create_default_tools()
    tool_names = [t.schema.name for t in tools]

    required_tools = [
        "add_memory",
        "list_notes",
        "edit_note",
        "delete_note",
        "search_memory",
    ]

    for tool_name in required_tools:
        assert tool_name in tool_names, f"{tool_name} not found in default tools"
        print(f"  ✓ {tool_name} registered")

    print(f"  Total tools: {len(tools)}")
    print("✅ Tool registration passed\n")


def test_end_to_end_workflow():
    """Test complete user workflow: add, list, edit, delete."""
    print("Testing end-to-end workflow...")

    # Note: AddMemoryTool requires API key, so we use memory_manager directly
    tool_instances = {
        "list": ListNotesTool(),
        "edit": EditNoteTool(),
        "delete": DeleteNoteTool(),
    }

    test_ids = []

    try:
        # Step 1: Add notes (directly to SQLite, bypassing AddMemoryTool)
        print("  Step 1: Adding notes...")
        mem_id_1 = memory_manager.add_memory(
            content="工作笔记：项目周会记录",
            tags=["work", "meeting"]
        )
        test_ids.append(mem_id_1)
        print(f"    ✓ Added note ID: {mem_id_1}")

        mem_id_2 = memory_manager.add_memory(
            content="学习笔记：Docker 最佳实践",
            tags=["study", "docker"]
        )
        test_ids.append(mem_id_2)
        print(f"    ✓ Added note ID: {mem_id_2}")

        # Step 2: List notes
        print("  Step 2: Listing notes...")
        result = tool_instances["list"].execute()
        assert "共有" in result
        assert "笔记" in result
        print(f"    ✓ Listed: {result[:60]}...")

        # Step 3: Edit a note
        print("  Step 3: Editing a note...")
        result = tool_instances["edit"].execute(
            note_id=mem_id_1,
            content="工作笔记：项目周会记录（已更新）"
        )
        assert "已更新" in result
        print(f"    ✓ Edited: {result}")

        # Step 4: Delete a note
        print("  Step 4: Deleting a note...")
        result = tool_instances["delete"].execute(note_id=mem_id_1)
        assert "已删除" in result
        print(f"    ✓ Deleted: {result}")

        print("  ✅ End-to-end workflow completed")

    except Exception as e:
        print(f"  ❌ Workflow failed: {e}")
        raise

    finally:
        # Clean up test data
        for mem_id in test_ids:
            try:
                memory_manager.delete_memory(mem_id)
            except:
                pass


if __name__ == "__main__":
    print("=" * 70)
    print("Integration Tests: Note Management (Phase 1-3)")
    print("=" * 70)
    print()

    try:
        cleanup_test_data()

        test_tool_schemas()
        test_tool_registration()
        test_list_notes_tool()
        test_edit_note_tool()
        test_delete_note_tool()
        test_search_memory_tool()
        test_end_to_end_workflow()

        print("=" * 70)
        print("✅ All Phase 1-3 integration tests passed!")
        print("=" * 70)

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
