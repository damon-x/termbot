#!/usr/bin/env python3
"""
Integration test for Phase 4: Updated tool layer.
"""
import sys
sys.path.insert(0, '.')

def test_new_tools_available():
    """Test that new memory tools are available."""
    print("Testing new tools availability...")

    from agent.tools.impl import AddMemoryTool, SearchMemoryTool

    add_tool = AddMemoryTool()
    search_tool = SearchMemoryTool()

    print(f"✓ AddMemoryTool: {add_tool.name}")
    print(f"  Schema: {add_tool.schema.description[:50]}...")
    print(f"✓ SearchMemoryTool: {search_tool.name}")
    print(f"  Schema: {search_tool.schema.description[:50]}...")

    # Test schema structure
    add_schema = add_tool.schema
    assert add_schema.name == "add_memory"
    assert len(add_schema.parameters) == 2
    assert add_schema.parameters[0].name == "content"
    assert add_schema.parameters[1].name == "tags"
    print("✓ AddMemoryTool schema structure correct")

    search_schema = search_tool.schema
    assert search_schema.name == "search_memory"
    assert len(search_schema.parameters) == 1
    assert search_schema.parameters[0].name == "queries"
    print("✓ SearchMemoryTool schema structure correct")

    print("\n✓ All Phase 4 tests passed!")


if __name__ == "__main__":
    try:
        test_new_tools_available()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
