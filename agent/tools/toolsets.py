"""
Tool set definitions for different Agent roles.

This module provides configuration-driven tool registration
for different Agent roles (main, skill, sub).

Each role declares its own complete tool set independently.
Shared tools are provided by _base_tools().
"""
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.tools.base import Tool


def get_toolset_for_role(
    role: str,
    agent_factory=None,
    **dependencies
) -> List['Tool']:
    """
    Get tool set for a specific role (excluding TerminalTool and file tools,
    which are registered separately by AgentFactory._create_agent).

    Args:
        role: Agent role ('main', 'skill', 'sub')
        agent_factory: AgentFactory (optional, for skill_executor / async_sub_agent)
        **dependencies: Tool dependencies (llm_client, skill_manager, allowed_tools, etc.)

    Returns:
        List of tools for the role
    """
    if role == "main":
        return _main_toolset(agent_factory, **dependencies)
    elif role == "skill":
        return _skill_toolset(**dependencies)
    elif role == "sub":
        return _sub_toolset(agent_factory, **dependencies)
    else:
        return []


def _base_tools() -> List['Tool']:
    """
    Tools shared by all agent roles: notes and file sending.
    """
    # pylint: disable=import-outside-toplevel
    from agent.tools.impl import (
        AddMemoryTool,
        SearchMemoryTool,
        SendFileTool,
        ListNotesTool,
        EditNoteTool,
        DeleteNoteTool,
    )
    return [
        AddMemoryTool(),
        SearchMemoryTool(),
        SendFileTool(),
        ListNotesTool(),
        EditNoteTool(),
        DeleteNoteTool(),
    ]


def _main_toolset(agent_factory=None, **deps) -> List['Tool']:
    """
    Tool set for main Agent.

    Base tools + use_skill + delegate_task.
    allowed_tools whitelist is applied at ReactLoop.register_tool time.
    """
    # pylint: disable=import-outside-toplevel
    tools = _base_tools()

    if agent_factory:
        from agent.tools.skill_executor import SkillExecutorTool
        from agent.tools.async_sub_agent import AsyncSubAgentTool
        allowed_tools = deps.get('allowed_tools')
        tools.append(SkillExecutorTool(agent_factory, allowed_tools=allowed_tools))
        tools.append(AsyncSubAgentTool(agent_factory))

    return tools


def _skill_toolset(**deps) -> List['Tool']:
    """
    Tool set for skill Agent.

    Base tools + use_skill_inject (inject-only, no sub-agent spawning).
    """
    # pylint: disable=import-outside-toplevel
    tools = _base_tools()

    skill_manager = deps.get('skill_manager')
    if skill_manager:
        from agent.tools.skill_inject import SkillInjectTool
        tools.append(SkillInjectTool(skill_manager))

    return tools


def _sub_toolset(agent_factory=None, **deps) -> List['Tool']:
    """
    Tool set for async sub Agent.

    Base tools + use_skill. Cannot create further sub agents.
    """
    # pylint: disable=import-outside-toplevel
    tools = _base_tools()

    if agent_factory:
        from agent.tools.skill_executor import SkillExecutorTool
        tools.append(SkillExecutorTool(agent_factory))

    return tools
