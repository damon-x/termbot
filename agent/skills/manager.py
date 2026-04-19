"""
Skill manager for discovering and loading skills.

This module provides SkillManager class that handles
skill discovery and hot-reload functionality.
"""
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING
import time

from agent.skills.skill import Skill
from agent.skills.loader import SkillLoader

if TYPE_CHECKING:
    from infrastructure.llm.client import OpenAIClient


class SkillManager:
    """
    Stateless skill manager with search cache and hot-reload support.

    Caches search results for 5 minutes to avoid repeated LLM calls.
    """

    CACHE_TTL = 300  # 5 minutes in seconds
    DEFAULT_SKILLS_DIR = Path.home() / ".termbot" / "skills"

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        """
        Initialize skill manager.

        Args:
            skills_dir: Path to skills directory. Defaults to ~/.termbot/skills/
        """
        self.skills_dir = skills_dir or self.DEFAULT_SKILLS_DIR
        self._search_cache: Dict[str, tuple[List[Dict], float]] = {}
        self._cache_timestamps: Dict[str, float] = {}

    def list_skill_basics(self) -> List[Dict]:
        """
        Scan all skills, returning only basic info (name + description).

        Returns:
            List of dicts with keys: name, description, path
        """
        if not self.skills_dir.exists():
            return []

        skills = []
        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            frontmatter = SkillLoader.parse_frontmatter(skill_md)
            if frontmatter and "name" in frontmatter and "description" in frontmatter:
                # Check if skill is enabled (default to True)
                enabled = frontmatter.get("enabled", True)
                if enabled:
                    skills.append({
                        "name": frontmatter["name"],
                        "description": frontmatter["description"],
                        "path": str(skill_path),
                        "execution_mode": frontmatter.get("execution_mode", "agent"),
                    })

        return skills

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """
        Get a skill by name (including full content).

        Hot-reload: Reads from filesystem on every call.

        Args:
            name: Skill name to look up

        Returns:
            Skill object, or None if not found
        """
        skills_basics = self.list_skill_basics()
        for basic in skills_basics:
            if basic["name"] == name:
                skill_path = Path(basic["path"])
                return SkillLoader.load_skill(skill_path)
        return None

    def search_skill_by_llm(
        self,
        llm_client: 'OpenAIClient',
        user_query: str,
        top_k: int = 3
    ) -> List[Dict]:
        """
        Use LLM to match user needs with skill descriptions.

        Includes 5-minute cache to avoid repeated LLM calls for same query.
        Falls back to keyword matching if LLM call fails.

        Args:
            llm_client: LLM client for matching
            user_query: User's need description
            top_k: Return top K most relevant skills

        Returns:
            List of matched skill basics (name, description, path)
        """
        import time

        # Check cache
        cache_key = f"search:{user_query}"
        current_time = time.time()

        if cache_key in self._search_cache:
            cache_time, cached_result = self._search_cache[cache_key]
            # Check if cache is still valid (within TTL)
            if current_time - cache_time < self.CACHE_TTL:
                # Return cached result
                return cached_result

        # Cache miss or expired - need to fetch
        skills_basics = self.list_skill_basics()

        if not skills_basics:
            return []

        # Build LLM prompt - list all available skills
        skill_list = "\n".join([
            f"- {s['name']}: {s['description']}"
            for s in skills_basics
        ])

        prompt = f"""You are a skill matching assistant. Find the most relevant skill for the user's needs.

User request: {user_query}

Available skills:
{skill_list}

IMPORTANT: If NO skill matches the user's request, return exactly "NONE" (don't force a match).
Otherwise, return only the skill name (e.g., "pyssh", not "/pyssh")."""

        try:
            # Call LLM to find matching skill
            response = llm_client.chat(
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse LLM response
            result = (response or "").strip()

            # Check if LLM said no match
            if result.upper() == "NONE":
                return []

            # Find matching skill by name
            for skill in skills_basics:
                if skill["name"].lower() == result.lower():
                    return [skill]

            # No exact match found
            return []

        except Exception as e:
            # LLM call failed - fall back to keyword matching
            query_lower = user_query.lower()
            matched = []

            for skill in skills_basics:
                if skill["name"].lower() in query_lower:
                    matched.append(skill)

            return matched
