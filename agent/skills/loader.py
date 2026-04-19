"""
Skill loader for parsing SKILL.md files.

This module provides the SkillLoader class that parses
YAML frontmatter and markdown content from SKILL.md files.
"""
import re
from pathlib import Path
from typing import Dict, Optional

import yaml

from agent.skills.skill import Skill


class SkillLoader:
    """
    SKILL.md file loader.

    Parses YAML frontmatter and markdown content from SKILL.md files
    to create Skill objects.
    """

    @staticmethod
    def parse_frontmatter(skill_md_path: Path) -> Optional[Dict]:
        """
        Parse YAML frontmatter from a SKILL.md file.

        Args:
            skill_md_path: Path to the SKILL.md file

        Returns:
            Dictionary with frontmatter data, or None if parsing fails
        """
        try:
            content = skill_md_path.read_text(encoding='utf-8')
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return None
            return yaml.safe_load(match.group(1))
        except Exception:
            return None

    @staticmethod
    def load_skill(skill_path: Path) -> Optional[Skill]:
        """
        Load a complete Skill from a skill directory.

        Args:
            skill_path: Path to the skill directory (containing SKILL.md)

        Returns:
            Skill object, or None if loading fails
        """
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding='utf-8')

            # Parse frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return None

            frontmatter = yaml.safe_load(match.group(1))

            # Validate required fields
            if not isinstance(frontmatter, dict):
                return None
            if "name" not in frontmatter or "description" not in frontmatter:
                return None

            # Extract markdown content (after frontmatter)
            markdown_content = content[match.end():].strip()

            # Replace ${SKILL_DIR} with the actual skill directory path
            markdown_content = markdown_content.replace("${SKILL_DIR}", str(skill_path))

            return Skill(
                name=frontmatter["name"],
                description=frontmatter["description"],
                content=markdown_content,
                path=skill_path,
                scripts_dir=skill_path / "scripts" if (skill_path / "scripts").exists() else None,
                references_dir=skill_path / "references" if (skill_path / "references").exists() else None,
                assets_dir=skill_path / "assets" if (skill_path / "assets").exists() else None,
                enabled=frontmatter.get("enabled", True),
                use_independent_pty=frontmatter.get("use_independent_pty", False),
                execution_mode=frontmatter.get("execution_mode", "agent"),
            )
        except Exception:
            return None
