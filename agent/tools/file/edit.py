"""
File Edit Tool - Edit files by replacing strings.

Replaces specific strings in files with support for single or
global replacement. Performs validation before editing.
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


class FileEditTool(Tool):
    """
    Tool for editing files by string replacement.

    Replaces old_string with new_string in a file.
    Supports single replacement or global replacement (replace_all).
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="edit_file",
            description=(
                "Edit a file by replacing a specific string with another string. "
                "Use this tool when you need to modify existing file contents. "
                "The tool will replace all occurrences of old_string with new_string. "
                "If you want to replace only the first occurrence, set replace_all to false. "
                "IMPORTANT: You must read the file first before editing it to understand "
                "the current content and ensure your edit is correct."
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type=ToolParameterType.STRING,
                    description=(
                        "The absolute path to the file to edit. "
                        "Must be an absolute path, not relative."
                    ),
                    required=True
                ),
                ToolParameter(
                    name="old_string",
                    type=ToolParameterType.STRING,
                    description=(
                        "The exact string to replace. "
                        "This string must exist in the file exactly as specified. "
                        "Make sure to include proper indentation and line breaks."
                    ),
                    required=True
                ),
                ToolParameter(
                    name="new_string",
                    type=ToolParameterType.STRING,
                    description=(
                        "The string to replace old_string with. "
                        "This will be inserted in place of old_string."
                    ),
                    required=True
                ),
                ToolParameter(
                    name="replace_all",
                    type=ToolParameterType.BOOLEAN,
                    description=(
                        "Whether to replace all occurrences of old_string. "
                        "If false (default), only the first occurrence is replaced. "
                        "If true, all occurrences are replaced."
                    ),
                    required=False,
                    default=False
                ),
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """
        Execute file editing.

        Args:
            **kwargs: Tool arguments (file_path, old_string, new_string, replace_all)

        Returns:
            Success message or error message
        """
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

        # Validate inputs
        if not file_path:
            return "❌ Error: file_path parameter is required"

        if old_string == "" and new_string == "":
            return "❌ Error: Both old_string and new_string are empty. No changes to make."

        if old_string == new_string:
            return "❌ Error: old_string and new_string are identical. No changes to make."

        try:
            # Normalize path
            normalized_path = normalize_path(file_path)

            # Check if file exists
            if not os.path.exists(normalized_path):
                # If old_string is empty, this is file creation
                if old_string == "":
                    # Create new file
                    ensure_directory_exists(normalized_path)
                    with open(normalized_path, 'w', encoding='utf-8') as f:
                        f.write(new_string)
                    return f"✅ File created: {file_path}"
                else:
                    return f"❌ Error: File does not exist: {file_path}"

            # Check if it's a directory
            if os.path.isdir(normalized_path):
                return f"❌ Error: Path is a directory, not a file: {file_path}"

            # Check for binary file
            if is_binary_file(normalized_path):
                return f"❌ Error: Cannot edit binary file: {file_path}"

            # Read current file content
            try:
                with open(normalized_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                return f"❌ Error reading file: {str(e)}"

            # Check if old_string exists in content
            if old_string and old_string not in content:
                return f"❌ Error: The string to replace was not found in the file.\nString: {old_string[:100]}{'...' if len(old_string) > 100 else ''}"

            # Count occurrences
            occurrences = content.count(old_string) if old_string else 0

            # Validate replace_all parameter
            if occurrences > 1 and not replace_all:
                return f"❌ Error: Found {occurrences} occurrences of the string.\nTo replace all occurrences, set replace_all to true.\nOr provide more context to uniquely identify the instance.\nString: {old_string[:100]}{'...' if len(old_string) > 100 else ''}"

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            # Write back to file
            try:
                with open(normalized_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except Exception as e:
                return f"❌ Error writing file: {str(e)}"

            # Generate summary
            lines_changed = abs(new_content.count('\n') - content.count('\n'))
            replace_msg = f"all {occurrences} occurrences" if replace_all else "1 occurrence"

            return (
                f"✅ File edited successfully: {file_path}\n"
                f"Replaced {replace_msg} of the string\n"
                f"Lines changed: approximately {lines_changed}"
            )

        except Exception as e:
            return f"❌ Error editing file: {str(e)}"
