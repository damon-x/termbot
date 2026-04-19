#!/usr/bin/env python3
"""
Unit tests for Phase 5: Unified memory tools only.

Tests tool registration and basic functionality.
"""
import sys
import os
sys.path.insert(0, '.')


def test_tool_imports():
    """Test that new tools can be imported."""
    print("Testing tool imports...")

    from agent.tools.impl import (
        AddMemoryTool,
        SearchMemoryTool,
    )
    print("✓ New tools imported successfully")


def test_tool_schemas():
    """Test that tool schemas are correct."""
    print("\nTesting tool schemas...")

    from agent.tools.impl import (
        AddMemoryTool,
        SearchMemoryTool,
    )

    # Test AddMemoryTool schema
    add_tool = AddMemoryTool()
    schema = add_tool.schema
    assert schema.name == "add_memory"
    assert "content" in str(schema.parameters)
    print("✓ AddMemoryTool schema verified")

    # Test SearchMemoryTool schema
    search_tool = SearchMemoryTool()
    schema = search_tool.schema
    assert schema.name == "search_memory"
    assert "queries" in str(schema.parameters)
    print("✓ SearchMemoryTool schema verified")


def test_tool_factory():
    """Test that tools are registered in factory."""
    print("\nTesting tool factory...")

    from agent.tools.impl import create_default_tools

    tools = create_default_tools()
    tool_names = [t.schema.name for t in tools]

    # New tools should be present
    assert "add_memory" in tool_names
    print("✓ AddMemoryTool registered in factory")

    assert "search_memory" in tool_names
    print("✓ SearchMemoryTool registered in factory")


def test_legacy_tools_removed():
    """Test that legacy tools have been removed."""
    print("\nTesting legacy tools removal...")

    from agent.tools.impl import create_default_tools

    tools = create_default_tools()
    tool_names = [t.schema.name for t in tools]

    # Legacy tools should NOT be present
    assert "add_note" not in tool_names
    assert "get_all_note" not in tool_names
    assert "create_quick_cmd" not in tool_names
    assert "get_all_quick_cmd" not in tool_names
    print("✓ Legacy tools removed from factory")


if __name__ == "__main__":
    print("=" * 60)
    print("Unit Tests: Phase 5 - Legacy Tools Removed")
    print("=" * 60)

    try:
        test_tool_imports()
        test_tool_schemas()
        test_tool_factory()
        test_legacy_tools_removed()

        print("\n" + "=" * 60)
        print("✅ All Phase 5 unit tests passed!")
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
