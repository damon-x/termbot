"""
File Tools Package - Core file operation tools.

Provides tools for reading, editing, and writing files.
Phase 1 implementation - basic functionality without permissions or user confirmation.
"""
from agent.tools.file.edit import FileEditTool
from agent.tools.file.read import FileReadTool
from agent.tools.file.write import FileWriteTool

__all__ = [
    'FileReadTool',
    'FileEditTool',
    'FileWriteTool',
]


def create_file_tools():
    """
    Create list of file tool instances.

    Returns:
        List of file tool instances
    """
    return [
        FileReadTool(),
        FileEditTool(),
        FileWriteTool(),
    ]
