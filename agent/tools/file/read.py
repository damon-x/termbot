"""
File Read Tool - Read file contents with line numbers and pagination.

Supports reading text files with optional offset/limit for pagination.
Automatically adds line numbers to output for easy reference.
"""
from typing import Any, Optional

from agent.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from agent.tools.file.utils import (
    add_line_numbers,
    format_file_size,
    is_binary_file,
    normalize_path,
    read_file_range,
    validate_file_path,
)


class FileReadTool(Tool):
    """
    Tool for reading file contents.

    Reads text files and returns content with line numbers.
    Supports pagination through offset/limit parameters.
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="read_file",
            description=(
                "Read the contents of a file. "
                "This tool can read any text file and display its contents with line numbers. "
                "Use this when you need to examine file contents, understand code structure, "
                "or reference specific parts of a file. "
                "For large files, use offset and limit to read specific portions."
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type=ToolParameterType.STRING,
                    description=(
                        "The absolute path to the file to read. "
                        "Must be an absolute path, not relative."
                    ),
                    required=True
                ),
                ToolParameter(
                    name="offset",
                    type=ToolParameterType.INTEGER,
                    description=(
                        "The line number to start reading from (1-indexed). "
                        "Only provide if the file is too large to read at once. "
                        "Default is 1 (start from beginning)."
                    ),
                    required=False,
                    default=1
                ),
                ToolParameter(
                    name="limit",
                    type=ToolParameterType.INTEGER,
                    description=(
                        "The number of lines to read. "
                        "Only provide if the file is too large to read at once. "
                        "If not specified, reads the entire file from offset."
                    ),
                    required=False
                ),
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """
        Execute file reading.

        Args:
            **kwargs: Tool arguments (file_path, offset, limit)

        Returns:
            File content with line numbers, or error message
        """
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit")

        # Validate inputs
        if not file_path:
            return "❌ Error: file_path parameter is required"

        # Convert offset to 0-indexed and ensure it's at least 1
        try:
            offset = max(1, int(offset))
        except (ValueError, TypeError):
            offset = 1

        if limit is not None:
            try:
                limit = max(1, int(limit))
            except (ValueError, TypeError):
                limit = None

        try:
            # Normalize and validate path
            normalized_path, _ = validate_file_path(file_path, must_exist=True)

            # Check if file exists
            if not os.path.exists(normalized_path):
                return f"❌ Error: File does not exist: {file_path}"

            # Check if it's a directory
            if os.path.isdir(normalized_path):
                return f"❌ Error: Path is a directory, not a file: {file_path}"

            # Check for binary file
            if is_binary_file(normalized_path):
                return f"❌ Error: Cannot read binary file: {file_path}"

            # Read file content with range
            content, lines_read, total_lines = read_file_range(
                normalized_path,
                offset=max(0, offset - 1),  # Convert to 0-indexed
                limit=limit
            )

            # Format output with line numbers
            if content:
                numbered_content = add_line_numbers(content, start_line=offset)

                # Add header information
                file_size = os.path.getsize(normalized_path)
                header = f"📄 {file_path} ({format_file_size(file_size)})"

                if limit is not None or offset > 1:
                    header += f" - Lines {offset}-{offset + lines_read - 1} of {total_lines}"

                result = f"{header}\n\n{numbered_content}"

                # Add truncation notice if applicable
                if limit is not None and offset + lines_read - 1 < total_lines:
                    result += f"\n\n... ({total_lines - offset - lines_read + 1} more lines)"

                return result
            else:
                # Empty file
                return f"📄 {file_path}\n\n⚠️ File is empty"

        except ValueError as e:
            return f"❌ Error: {str(e)}"
        except Exception as e:
            return f"❌ Error reading file: {str(e)}"


# Import os module for file operations
import os
