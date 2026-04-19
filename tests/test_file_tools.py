"""
Test script for file tools.

Basic tests to verify FileReadTool, FileEditTool, and FileWriteTool functionality.
"""
import os
import sys
import tempfile

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agent.tools.file import FileReadTool, FileEditTool, FileWriteTool


def test_file_write_tool():
    """Test FileWriteTool - create new file."""
    print("🧪 Testing FileWriteTool...")

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_file = f.name

    try:
        tool = FileWriteTool()
        result = tool.execute(
            file_path=test_file,
            content="Hello, World!\nThis is a test file.\nIt has multiple lines."
        )

        print(f"Result: {result}")
        assert "created successfully" in result.lower() or "written" in result.lower()
        print("✅ FileWriteTool test passed\n")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_file_read_tool():
    """Test FileReadTool - read existing file."""
    print("🧪 Testing FileReadTool...")

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_file = f.name
        f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

    try:
        tool = FileReadTool()
        result = tool.execute(file_path=test_file)

        print(f"Result:\n{result}")
        assert "Line 1" in result
        assert "Line 5" in result
        assert "→" in result  # Line number prefix
        print("✅ FileReadTool test passed\n")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_file_read_with_offset_limit():
    """Test FileReadTool with offset and limit parameters."""
    print("🧪 Testing FileReadTool with offset/limit...")

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_file = f.name
        for i in range(1, 11):
            f.write(f"Line {i}\n")

    try:
        tool = FileReadTool()
        result = tool.execute(file_path=test_file, offset=3, limit=3)

        print(f"Result:\n{result}")
        assert "Line 3" in result
        assert "Line 5" in result
        assert "Line 6" not in result  # Should be limited
        print("✅ FileReadTool offset/limit test passed\n")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_file_edit_tool():
    """Test FileEditTool - replace string in file."""
    print("🧪 Testing FileEditTool...")

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_file = f.name
        f.write("Hello, World!\nThis is a test file.\nGoodbye, World!")

    try:
        tool = FileEditTool()
        result = tool.execute(
            file_path=test_file,
            old_string="World",
            new_string="Universe",
            replace_all=True
        )

        print(f"Result: {result}")
        assert "edited successfully" in result.lower()

        # Verify the change
        with open(test_file, 'r') as f:
            content = f.read()
            assert "Universe" in content
            assert "World" not in content

        print("✅ FileEditTool test passed\n")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_file_overwrite():
    """Test FileWriteTool - overwrite existing file."""
    print("🧪 Testing FileWriteTool overwrite...")

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        test_file = f.name
        f.write("Original content")

    try:
        tool = FileWriteTool()
        result = tool.execute(
            file_path=test_file,
            content="New content"
        )

        print(f"Result: {result}")

        # Verify the overwrite
        with open(test_file, 'r') as f:
            content = f.read()
            assert content == "New content"

        print("✅ FileWriteTool overwrite test passed\n")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_nonexistent_file():
    """Test error handling for non-existent file."""
    print("🧪 Testing error handling...")

    tool = FileReadTool()
    result = tool.execute(file_path="/nonexistent/file.txt")

    print(f"Result: {result}")
    assert "does not exist" in result.lower() or "error" in result.lower()
    print("✅ Error handling test passed\n")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("🚀 Starting File Tools Tests")
    print("=" * 60 + "\n")

    try:
        test_file_write_tool()
        test_file_read_tool()
        test_file_read_with_offset_limit()
        test_file_edit_tool()
        test_file_overwrite()
        test_nonexistent_file()

        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
