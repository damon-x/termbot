"""
Skill system for TermBot.

This package provides the skill infrastructure:
- Skill: Data class for skills
- SkillLoader: Parser for SKILL.md files
- SkillManager: Manager for skill discovery and loading
"""
from agent.skills.skill import Skill
from agent.skills.loader import SkillLoader
from agent.skills.manager import SkillManager

__all__ = [
    "Skill",
    "SkillLoader",
    "SkillManager",
]
