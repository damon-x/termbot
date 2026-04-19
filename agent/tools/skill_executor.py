"""
Skill Executor Tool - Creates skill agents to execute specialized tasks.

This tool enables the main Agent to delegate specialized work to
skill agents that have their own context and instructions.
"""
from typing import TYPE_CHECKING

from agent.tools.base import Tool, ToolParameter, ToolParameterType, ToolSchema

if TYPE_CHECKING:
    from agent.factory import AgentFactory


class SkillExecutorTool(Tool):
    """
    Tool for executing tasks using specialized skill agents.

    The main Agent calls this tool to delegate work to a skill agent
    with its own context and instructions from SKILL.md.
    """

    def __init__(self, agent_factory, allowed_tools=None) -> None:
        """
        Initialize the skill executor tool.

        Args:
            agent_factory: Factory for creating skill agents
            allowed_tools: Inherited from main agent, passed to skill agents
        """
        self.agent_factory = agent_factory
        self.allowed_tools = allowed_tools
        self._schema = ToolSchema(
            name="use_skill",
            description=(
                "Execute a task using the specified skill. Skills have two execution modes:\n"
                "\n"
                "**[agent mode]**: A dedicated sub-agent runs the task with the skill's instructions. "
                "Call once with full task context and wait for the result.\n"
                "\n"
                "**[inject mode]**: The skill returns its instructions directly to you. "
                "After the call, read the instructions and execute the task yourself using other tools (e.g. exec_terminal_cmd). "
                "Do NOT call use_skill again for the same skill — one call is enough to get the instructions.\n"
                "\n"
                "【Task Description Principles】\n"
                "1. Describe the user's COMPLETE INTENT/GOAL, not just the first step\n"
                "2. Include target environment, operations to perform, and expected outcome\n"
                "3. One task = one coherent workflow; split independent goals into separate calls"
            ),
            parameters=[
                ToolParameter(
                    name="skill_name",
                    type=ToolParameterType.STRING,
                    description="Skill name (without / prefix)",
                    required=True
                ),
                ToolParameter(
                    name="task",
                    type=ToolParameterType.STRING,
                    description=(
                        "Task description: Include complete goals and context for the skill to understand what result to achieve. "
                        "Include: target server/environment, operations to perform, expected results. "
                        "Don't just give the first step - provide the complete intent."
                    ),
                    required=True
                )
            ]
        )

    @property
    def schema(self) -> ToolSchema:
        """Get the tool schema."""
        return self._schema

    def execute(self, skill_name: str, task: str) -> str:
        """
        Execute a task using the specified skill.

        Args:
            skill_name: Name of the skill to use
            task: Specific task to execute

        Returns:
            Result from skill agent execution
        """
        from infrastructure.logging import get_logger, logger_context
        logger = get_logger("skill.executor")

        # Save current agent_id to restore later
        current_agent_id = logger_context.get("agent_id", "main")

        # Remove "/" prefix if present (LLM may include it from skill list display)
        if skill_name.startswith("/"):
            skill_name = skill_name[1:]

        # Hot-reload: Read from filesystem each time
        skill = self.agent_factory.skill_manager.get_skill_by_name(skill_name)

        if not skill:
            return f"Skill '{skill_name}' 未找到"

        # inject mode: return full skill content directly to main agent
        if skill.execution_mode == "inject":
            logger.info(f"💉 Inject Mode [{skill_name}]: returning skill content to main agent")
            return (
                f"[Skill: {skill.name} - Instructions Loaded]\n"
                f"The skill instructions have been loaded. No action has been taken yet.\n"
                f"IMPORTANT: Do NOT call use_skill again. You must now execute the task yourself "
                f"using tools like exec_terminal_cmd based on the instructions below:\n\n"
                f"{skill.content}"
            )

        # Create skill agent, inheriting allowed_tools from main agent (minus use_skill)
        skill_agent = self.agent_factory.create_skill_agent(skill, self.allowed_tools)

        try:
            # INFO 级别：打印 sub agent 的提示词（system prompt）
            system_prompt = skill_agent.react_loop.system_prompt
            prompt_preview = system_prompt[:400] + "..." if len(system_prompt) > 400 else system_prompt
            logger.info(f"🤖 Sub Agent Prompt [{skill_name}]:\n{prompt_preview}")

            # INFO 级别：打印给 sub agent 的任务
            logger.info(f"📝 Sub Agent Task [{skill_name}]: {task}")

            result = skill_agent.process_message_with_result(task)

            # INFO 级别：打印 sub agent 的输出
            response_preview = result.response[:400] + "..." if len(result.response) > 400 else result.response
            logger.info(f"✨ Sub Agent Response [{skill_name}]:\n{response_preview}")

            if result.success:
                return result.response
            else:
                return f"执行失败: {result.error or '未知错误'}"
        except Exception as e:
            logger.error(f"Sub Agent execution failed [{skill_name}]", error=str(e))
            return f"执行出错: {e}"
        finally:
            # Restore main agent's agent_id in logging context
            logger_context.set_agent(agent_id=current_agent_id)
