"""
Async Sub Agent Tool - Creates async sub agents to execute tasks in parallel.

This tool enables the main Agent to delegate tasks to sub agents
that run asynchronously and report back when complete.
"""
from typing import TYPE_CHECKING, Any, List, Optional

from agent.tools.base import Tool, ToolParameter, ToolParameterType, ToolSchema

if TYPE_CHECKING:
    from agent.factory import AgentFactory
    from agent.core import Agent


class AsyncSubAgentTool(Tool):
    """
    Tool for creating async sub agents to execute tasks.

    The main Agent calls this tool to delegate tasks that can run
    independently. The tool creates sub agents, queues their tasks,
    and returns immediately without blocking.

    Sub agents:
    - Run in their own worker threads
    - Report results back via AgentReplyHandler
    - Can use skills but cannot create nested sub agents
    """

    def __init__(self, agent_factory: 'AgentFactory') -> None:
        """
        Initialize the async sub agent tool.

        Args:
            agent_factory: Factory for creating sub agents
        """
        self.agent_factory = agent_factory
        self._main_agent: Optional['Agent'] = None
        self._task_counter = 0
        self._schema = ToolSchema(
            name="delegate_task",
            description=(
                "将任务委派给异步子代理执行。"
                "适用于：需要并行执行的独立任务、耗时较长的操作、可以拆分的复杂任务。"
                "\n\n"
                "【使用场景】"
                "✅ 多个独立任务可以并行执行"
                "✅ 单个任务耗时较长，不希望阻塞主流程"
                "✅ 用户请求可以拆分为多个子任务"
                "\n"
                "【注意事项】"
                "- 子代理完成后会自动将结果发回主代理"
                "- 每个子代理独立运行，无法相互通信"
                "- 子代理可以使用技能，但不能创建更多子代理"
                "- 立即返回，不等待结果"
            ),
            parameters=[
                ToolParameter(
                    name="tasks",
                    type=ToolParameterType.ARRAY,
                    description=(
                        "要委派的任务列表。每个任务是一个对象，包含："
                        "\n- task: 任务描述（必填）"
                        "\n- system_prompt: 自定义提示词（可选）"
                    ),
                    required=True
                ),
                ToolParameter(
                    name="parallel",
                    type=ToolParameterType.BOOLEAN,
                    description="是否并行执行多个任务（默认 true）",
                    required=False,
                    default=True
                )
            ]
        )

    @property
    def schema(self) -> ToolSchema:
        """Get the tool schema."""
        return self._schema

    def set_agent(self, agent: 'Agent') -> None:
        """
        Set the main agent reference.

        Called by Agent.register_tool() during setup.

        Args:
            agent: The main Agent instance
        """
        self._main_agent = agent

    def execute(self, **kwargs: Any) -> str:
        """
        Create sub agents and queue tasks.

        Args:
            tasks: List of task objects
            parallel: Whether to run in parallel (default True)

        Returns:
            Confirmation message
        """
        from infrastructure.logging import get_logger
        logger = get_logger("tool.delegate_task")

        tasks = kwargs.get("tasks", [])
        parallel = kwargs.get("parallel", True)

        if not tasks:
            return "没有提供任务"

        if not self._main_agent:
            return "错误：主代理引用未设置"

        # Validate tasks format
        if not isinstance(tasks, list):
            return "错误：tasks 必须是数组"

        results = []
        for task_item in tasks:
            if isinstance(task_item, dict):
                task_desc = task_item.get("task", "")
                system_prompt = task_item.get("system_prompt")
            else:
                task_desc = str(task_item)
                system_prompt = None

            if not task_desc:
                continue

            # Generate task ID
            self._task_counter += 1
            task_id = str(self._task_counter)

            # Create sub agent with reply handler pointing to main agent
            sub_agent = self.agent_factory.create_sub_agent(
                parent_agent=self._main_agent,
                task_id=task_id,
                task_description=task_desc,
                system_prompt=system_prompt
            )

            # Submit task to sub agent's queue - returns immediately
            sub_agent.submit(task_desc)

            logger.info(
                "Sub agent created and task submitted",
                task_id=task_id,
                task_preview=task_desc[:50]
            )

            results.append(f"任务 #{task_id}: {task_desc[:50]}...")

        # Return immediately - sub agents will report back later
        if len(results) == 1:
            return f"已创建子代理执行任务\n{results[0]}"
        else:
            return f"已创建 {len(results)} 个子代理并行执行任务:\n" + "\n".join(results)