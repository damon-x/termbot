"""
Skill data classes for the skill system.

This module defines the data structures used to represent
user-defined skills loaded from SKILL.md files.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    """
    Skill data class.

    Represents a user-defined skill with metadata and content
    loaded from a SKILL.md file.
    """
    name: str
    description: str
    content: str
    path: Path
    scripts_dir: Optional[Path] = None
    references_dir: Optional[Path] = None
    assets_dir: Optional[Path] = None
    enabled: bool = True
    use_independent_pty: bool = False
    execution_mode: str = "agent"  # "agent" | "inject"

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, path={self.path}, enabled={self.enabled})"
