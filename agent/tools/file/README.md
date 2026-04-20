# File Tools - Phase 1 Implementation

Core file operation tools for TermBot, implemented in Python.

## 📋 Overview

This package provides three essential file operation tools:

1. **FileReadTool** - Read file contents with line numbers and pagination
2. **FileEditTool** - Edit files by string replacement
3. **FileWriteTool** - Create or overwrite files

## 🚀 Features

### FileReadTool
- ✅ Read text files with automatic line numbering
- ✅ Pagination support via `offset` and `limit` parameters
- ✅ Binary file detection and rejection
- ✅ File size information display
- ✅ Empty file handling
- ✅ Clear error messages for missing files

### FileEditTool
- ✅ Replace exact strings in files
- ✅ Single or global replacement (`replace_all` parameter)
- ✅ String existence validation before editing
- ✅ Multiple occurrence detection
- ✅ Binary file protection
- ✅ Create new files with empty `old_string`

### FileWriteTool
- ✅ Create new files automatically
- ✅ Overwrite existing files
- ✅ Automatic parent directory creation
- ✅ Binary file protection
- ✅ Clear success/error reporting
- ✅ File statistics (lines, size)

## 📁 Directory Structure

```
agent/tools/file/
├── __init__.py      # Package initialization and exports
├── read.py          # FileReadTool implementation
├── edit.py          # FileEditTool implementation
├── write.py         # FileWriteTool implementation
├── utils.py         # Shared utility functions
└── README.md        # This file
```

## 🔧 Usage

### Basic Example

```python
from agent.tools.file import FileReadTool, FileEditTool, FileWriteTool

# Write a new file
write_tool = FileWriteTool()
result = write_tool.execute(
    file_path="/tmp/example.txt",
    content="Hello, World!\nThis is a test file."
)
print(result)

# Read the file
read_tool = FileReadTool()
result = read_tool.execute(file_path="/tmp/example.txt")
print(result)

# Edit the file
edit_tool = FileEditTool()
result = edit_tool.execute(
    file_path="/tmp/example.txt",
    old_string="World",
    new_string="Universe",
    replace_all=True
)
print(result)
```

### Reading with Pagination

```python
# Read specific line ranges
read_tool = FileReadTool()

# Read lines 10-20
result = read_tool.execute(
    file_path="/tmp/large_file.txt",
    offset=10,   # Start from line 10
    limit=11     # Read 11 lines (10-20)
)
print(result)
```

### Editing Files

```python
edit_tool = FileEditTool()

# Replace first occurrence only
result = edit_tool.execute(
    file_path="/tmp/config.py",
    old_string="DEBUG = True",
    new_string="DEBUG = False",
    replace_all=False  # Only first match
)

# Replace all occurrences
result = edit_tool.execute(
    file_path="/tmp/config.py",
    old_string="TODO",
    new_string="DONE",
    replace_all=True  # All matches
)
```

## 🧪 Testing

Run the test suite:

```bash
# From project root
.venv/bin/python tests/test_file_tools.py
```

Run the demonstration:

```bash
.venv/bin/python examples/file_tools_demo.py
```

## 🔍 Tool Schemas

### FileReadTool Schema

```json
{
  "name": "read_file",
  "description": "Read the contents of a file with line numbers",
  "parameters": {
    "file_path": "string (required) - Absolute path to file",
    "offset": "integer (optional) - Starting line number (default: 1)",
    "limit": "integer (optional) - Number of lines to read"
  }
}
```

### FileEditTool Schema

```json
{
  "name": "edit_file",
  "description": "Edit a file by replacing strings",
  "parameters": {
    "file_path": "string (required) - Absolute path to file",
    "old_string": "string (required) - String to replace",
    "new_string": "string (required) - Replacement string",
    "replace_all": "boolean (optional) - Replace all occurrences (default: false)"
  }
}
```

### FileWriteTool Schema

```json
{
  "name": "write_file",
  "description": "Write or create a file with content",
  "parameters": {
    "file_path": "string (required) - Absolute path to file",
    "content": "string (required) - Content to write"
  }
}
```

## 🎯 Design Principles

1. **Simplicity First** - Basic functionality without complex features
2. **Clear Errors** - Helpful error messages for common issues
3. **Safety** - Binary file protection and validation
4. **Consistency** - Uniform API across all tools
5. **Performance** - Efficient file operations

## ⚠️ Limitations (Phase 1)

Current implementation does NOT include:

- ❌ Permission checking
- ❌ User confirmation dialogs
- ❌ File modification time tracking
- ❌ Concurrent edit protection
- ❌ Git integration
- ❌ File type detection (images, PDFs, notebooks)
- ❌ Content caching/deduplication

These features are planned for future phases.

## 🔄 Integration with Agent

To integrate these tools into the Agent system:

```python
# In agent/core.py or tools initialization
from agent.tools.file import create_file_tools

class Agent:
    def __init__(self):
        # ... existing initialization ...
        self._register_file_tools()

    def _register_file_tools(self):
        """Register file operation tools."""
        from agent.tools.file import FileReadTool, FileEditTool, FileWriteTool

        for tool in [FileReadTool(), FileEditTool(), FileWriteTool()]:
            self.tool_registry.register(tool)
```

## 📊 Implementation Notes

### Path Handling
- All paths are normalized to absolute paths
- User directory expansion (`~`) is supported
- Path validation happens before file operations

### File Encoding
- Default encoding: UTF-8
- Error handling: `replace` mode (replace invalid bytes)
- Line endings: Preserved as-is (no CRLF conversion)

### Memory Management
- No file size limits in Phase 1
- Large files should be read with pagination
- Entire file contents loaded into memory

### Error Handling
- All exceptions caught and converted to user-friendly messages
- Error messages prefixed with ❌ for easy identification
- Success messages prefixed with ✅

## 🚀 Next Steps

### Phase 2: Search Tools
- Implement `GrepTool` for content search
- Implement `GlobTool` for file pattern matching

### Phase 3: Enhanced Features
- Add permission system
- Implement user confirmation dialogs
- Add file modification time tracking
- Concurrent edit protection

### Phase 4: Advanced File Types
- Image file support (read, resize)
- PDF file support
- Jupyter notebook support

## 📝 Code Style

- Follows PEP 8 conventions
- Type hints where applicable
- Comprehensive docstrings
- Clear variable names
- Consistent error handling

## 🤝 Contributing

When adding new features:

1. Implement the tool in appropriate file
2. Add corresponding tests in `tests/test_file_tools.py`
3. Update this README with new features
4. Run tests to ensure no regressions

## 📄 License

Part of the TermBot project.
