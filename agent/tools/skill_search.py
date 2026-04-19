"""
Skill Search Tool - Uses LLM to find matching skills.

This tool enables the main Agent to discover available skills
based on user queries using natural language matching.
"""
from typing import TYPE_CHECKING

from agent.tools.base import Tool, ToolParameter, ToolParameterType, ToolSchema

if TYPE_CHECKING:
    from agent.skills import SkillManager
    from infrastructure.llm.client import OpenAIClient


class SkillSearchTool(Tool):
    """
    Tool for searching skills using LLM matching.

    The main Agent calls this tool during ReAct loop when it needs
    specialized capabilities. The LLM matches the user's query
    against available skill descriptions.
    """

    def __init__(
        self,
        skill_manager,
        llm_client
    ) -> None:
        """
        Initialize the skill search tool.

        Args:
            skill_manager: SkillManager instance for finding skills
            llm_client: OpenAIClient for LLM-based matching
        """
        self.skill_manager = skill_manager
        self.llm_client = llm_client
        self._schema = ToolSchema(
            name="search_skill",
            description=(
                "IMPORTANT: When user needs to connect to remote servers (SSH), perform specialized operations, "
                "or handle domain-specific tasks (PDF processing, Git workflows, data analysis, etc.), "
                "ALWAYS search for matching skills FIRST before attempting direct commands."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="Type of skill or capability needed (e.g., 'SSH connection', 'PDF processing', 'Git workflow')",
                    required=True
                )
            ]
        )

    @property
    def schema(self) -> ToolSchema:
        """Get the tool schema."""
        return self._schema

    def execute(self, query: str) -> str:
        """
        Search for matching skills.

        Args:
            query: User's query describing needed capability

        Returns:
            Formatted result with matching skills
        """
        matched = self.skill_manager.search_skill_by_llm(
            self.llm_client,
            query
        )

        if not matched:
            return f"未找到与 '{query}' 相关的 skill"

        result = f"找到 {len(matched)} 个相关 skill:\n"
        for skill in matched:
            result += f"\n- /{skill['name']}: {skill['description']}"

        return result
