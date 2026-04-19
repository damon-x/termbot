"""
File Write Tool - Write or create files with content.

Writes content to files, creating new files or overwriting
existing ones. Handles directory creation automatically.
"""
import os
from typing import Any

from agent.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from agent.tools.file.utils import (
    ensure_directory_exists,
    is_binary_file,
    normalize_path,
)


class FileWriteTool(Tool):
    """
    Tool for writing or creating files.

    Writes content to a file, creating it if it doesn't exist
    or overwriting if it does. Automatically creates parent directories.
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="write_file",
            description=(
                "Write content to a file, creating it if it doesn't exist "
                "or overwriting it if it does. "
                "Use this tool when you need to create a new file or completely "
                "replace the contents of an existing file. "
                "IMPORTANT: This will overwrite existing files without warning. "
                "If you want to modify specific parts of a file, use edit_file instead. "
                "Parent directories are created automatically if they don't exist."
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type=ToolParameterType.STRING,
                    description=(
                        "The absolute path to the file to write. "
                        "Must be an absolute path, not relative. "
                        "Parent directories will be created if they don't exist."
                    ),
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type=ToolParameterType.STRING,
                    description=(
                        "The content to write to the file. "
                        "This will completely replace any existing content."
                    ),
                    required=True
                ),
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """
        Execute file writing.

        Args:
            **kwargs: Tool arguments (file_path, content)

        Returns:
            Success message or error message
        """
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        # Validate inputs
        if not file_path:
            return "❌ Error: file_path parameter is required"

        if content is None:
            content = ""

        try:
            # Normalize path
            normalized_path = normalize_path(file_path)

            # Check if path already exists as a directory
            if os.path.exists(normalized_path) and os.path.isdir(normalized_path):
                return f"❌ Error: Path exists as a directory: {file_path}"

            # Check if this is a binary file extension (prevent accidental writes)
            if is_binary_file(normalized_path):
                return f"❌ Error: Cannot write to binary file: {file_path}"

            # Check if file exists for reporting
            file_exists = os.path.exists(normalized_path)

            # Ensure parent directory exists
            ensure_directory_exists(normalized_path)

            # Write content to file
            try:
                with open(normalized_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                return f"❌ Error writing file: {str(e)}"

            # Generate summary
            line_count = content.count('\n') + 1 if content else 0
            file_size = len(content.encode('utf-8'))

            if file_exists:
                action = "overwritten"
                verb = "overwrote"
            else:
                action = "created"
                verb = "created"

            return (
                f"✅ File {action} successfully: {file_path}\n"
                f"Lines written: {line_count}\n"
                f"Size: {file_size} bytes"
            )

        except Exception as e:
            return f"❌ Error writing file: {str(e)}"
