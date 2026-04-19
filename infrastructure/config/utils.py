"""
Utility functions for configuration and common operations.
"""
import json
import uuid
from pathlib import Path
from typing import Any

from infrastructure.config.settings import settings


def get_prompt(name: str) -> str:
    """
    Get prompt template by name.

    Args:
        name: Prompt name

    Returns:
        Prompt template string

    Raises:
        FileNotFoundError: If prompts file doesn't exist
        ValueError: If prompt not found
    """
    prompts_path = Path("agent/prompts/templates.txt")
    if not prompts_path.exists():
        # Fallback to old location
        prompts_path = Path("bot/prompts.txt")

    with open(prompts_path, "r", encoding="utf-8") as f:
        content = f.read()

    prompts = content.split("::prompt")
    for prompt in prompts:
        parts = prompt.split("::content")
        title = parts[0].strip()
        if title == name:
            result = ""
            for line in parts[1].strip().split("\n"):
                if not line.strip().startswith("//"):
                    result = result + "\n" + line
            return result

    raise ValueError(f"Prompt '{name}' not found")


def get_config(key: str) -> Any:
    """
    Get configuration value.

    Args:
        key: Configuration key (supports dot notation)

    Returns:
        Configuration value or None if not found
    """
    return settings.get(key)


def save_tmp_file(data: str, ext: str) -> str:
    """
    Save data to temporary file.

    Args:
        data: Content to save
        ext: File extension

    Returns:
        Generated filename
    """
    file_name = f"{uuid.uuid4().hex[:10]}.{ext}"
    with open(f"/tmp/{file_name}", "w", encoding="utf-8") as f:
        f.write(data)
    return file_name


def get_tmp_file(file_name: str) -> str:
    """
    Read content from temporary file.

    Args:
        file_name: Filename to read

    Returns:
        File content or empty string if error
    """
    try:
        with open(f"/tmp/{file_name}", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
