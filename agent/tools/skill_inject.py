"""
Skill Inject Tool - Loads skill instructions into the current agent context.

Used exclusively by skill agents to reference other skills in inject mode only.
No sub-agent is created; the calling agent receives the skill's instructions
and executes the task itself.
"""
from agent.tools.base import Tool, ToolParameter, ToolParameterType, ToolSchema

if False:  # TYPE_CHECKING
    from agent.skills.manager import SkillManager


class SkillInjectTool(Tool):
    """
    Tool for loading another skill's instructions into the current agent.

    Only supports inject mode: returns the target skill's content so the
    calling agent can execute the task itself. Never spawns a sub-agent.
    """

    def __init__(self, skill_manager: 'SkillManager') -> None:
        self.skill_manager = skill_manager
        self._schema = ToolSchema(
            name="use_skill_inject",
            description=(
                "Load another skill's instructions into your current context. "
                "The skill's content will be returned to you directly — "
                "read it carefully and execute the task yourself using your available tools. "
                "Do NOT call use_skill_inject again for the same skill after receiving its instructions."
            ),
            parameters=[
                ToolParameter(
                    name="skill_name",
                    type=ToolParameterType.STRING,
                    description="Skill name to load (without / prefix)",
                    required=True
                )
            ]
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    def execute(self, skill_name: str) -> str:
        from infrastructure.logging import get_logger
        logger = get_logger("skill.inject")

        if skill_name.startswith("/"):
            skill_name = skill_name[1:]

        skill = self.skill_manager.get_skill_by_name(skill_name)
        if not skill:
            return f"Skill '{skill_name}' 未找到"

        logger.info(f"💉 Skill Inject [{skill_name}]: loading instructions into skill agent")
        return (
            f"[Skill: {skill.name} - Instructions Loaded]\n"
            f"IMPORTANT: Do NOT call use_skill_inject again. "
            f"Execute the task yourself using your available tools based on the instructions below:\n\n"
            f"{skill.content}"
        )
