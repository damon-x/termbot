"""
Agent Factory for creating different role-based agents.

This module provides AgentFactory class that creates
main and skill agents with shared PTY Manager.
"""
from typing import TYPE_CHECKING, Optional

from agent.core import Agent, AgentConfig
from agent.response_handler import AgentReplyHandler, ResponseHandler
from agent.tools.toolsets import get_toolset_for_role
from agent.tools.terminal import TerminalTool, TerminalBufferTool
from agent.tools.file import create_file_tools

if TYPE_CHECKING:
    from infrastructure.terminal.pty_manager import PTYManager
    from infrastructure.llm.client import OpenAIClient
    from agent.skills import SkillManager
    from agent.skills.skill import Skill


class AgentFactory:
    """
    Factory for creating Agent instances.

    PTY Sharing: All agents (main + skill) use the same PTY.
    Context Isolation: Each agent has independent Context.
    """

    def __init__(
        self,
        pty_manager: 'PTYManager',
        skill_manager: 'SkillManager',
        llm_client: 'OpenAIClient'
    ) -> None:
        """
        Initialize the factory.

        Args:
            pty_manager: Shared PTY Manager for all agents
            skill_manager: Skill Manager for skill discovery
            llm_client: LLM Client
        """
        self.pty_manager = pty_manager
        self.skill_manager = skill_manager
        self.llm_client = llm_client

    def create_main_agent(
        self,
        system_prompt: Optional[str] = None,
        response_handler: Optional[ResponseHandler] = None,
        allowed_tools: Optional[list] = None,
        allowed_skills: Optional[list] = None,
        agent_id: Optional[str] = None
    ) -> Agent:
        """
        Create main agent (using shared PTY).

        Args:
            system_prompt: Optional custom system prompt
            response_handler: Optional handler for async responses
            allowed_tools: Optional list of allowed tool names (empty = all)
            allowed_skills: Optional list of allowed skill names (empty = all)
            agent_id: Agent Profile ID for context injection (e.g. "default")

        Returns:
            Configured main Agent instance
        """
        config = AgentConfig(
            llm_client=self.llm_client,
            max_iterations=20,
            enable_memory=True,
            role="main",
            system_prompt=system_prompt,
            pty_manager=self.pty_manager,
            skill_manager=self.skill_manager,
            tools=get_toolset_for_role(
                "main",
                agent_factory=self,
                skill_manager=self.skill_manager,
                llm_client=self.llm_client,
                allowed_tools=allowed_tools,
            ),
            allowed_skills=allowed_skills,
            allowed_tools=allowed_tools,
            response_handler=response_handler
        )
        agent = self._create_agent(config, instance_id="main")
        if agent_id:
            agent.set_agent_id(agent_id)
        return agent

    def create_skill_agent(self, skill: 'Skill', allowed_tools: Optional[list] = None) -> Agent:
        """
        Create skill agent.

        Args:
            skill: Skill object with content

        Returns:
            Configured skill Agent instance
        """
        from infrastructure.terminal.pty_manager import PTYManager
        from infrastructure.logging import get_logger

        logger = get_logger("factory.skill_agent")

        # Determine PTY: independent or shared
        if skill.use_independent_pty:
            # Create independent PTY for this skill agent
            skill_pty = PTYManager()
            skill_pty.start()
            pty_manager = skill_pty
            logger.info(f"Created independent PTY for skill agent: {skill.name}")
        else:
            # Use shared PTY
            pty_manager = self.pty_manager
            logger.info(f"Using shared PTY for skill agent: {skill.name}")

        # Build skill system prompt
        skill_system_prompt = f"""# Skill: {skill.name}

{skill.description}

## Skill Directory
This skill is located at: {skill.path}
IMPORTANT: When you see instructions mentioning scripts, use the full path above.

## Working with Skill Scripts (If Applicable)

If the skill instructions mention running scripts or helper tools:
1. First, explore the skill directory to understand its structure:
   - List the skill directory: ls -la {skill.path}/
   - Look for subdirectories like: scripts/, tools/, bin/

2. Verify the script exists before running:
   - Example: ls -la {skill.path}/scripts/
   - Make sure the file is actually there

3. Use the FULL PATH when executing (not relative paths):
   - Correct: python3 {skill.path}/scripts/system_info.py
   - Wrong: python3 scripts/system_info.py (will fail)

4. If a script mentioned in instructions is not found:
   - Report: "Expected script at {skill.path}/scripts/xxx.py but not found"
   - Ask the user for guidance
   - Do not make up paths - always verify with ls first

## Response Guidelines (IMPORTANT)

When responding to the user, follow these rules:

1. **Summarize results in natural language** - Do NOT simply repeat command output or error messages
2. **When a command fails:**
   - Explain what went wrong in plain language
   - Analyze the possible cause
   - Suggest next steps or alternatives
   - Example: Instead of "Error: pods 'xxx' not found", say "Pod 'xxx' 不存在，可能原因：1) Pod 名称有误 2) 在错误的 namespace 中。建议先执行 kubectl get pods -n <namespace> 查看实际的 Pod 列表"
3. **When a command succeeds:**
   - Summarize the key findings
   - Highlight important information
   - Do NOT dump raw output unless specifically requested
4. **Be concise but helpful** - Focus on what the user needs to know

## Instructions

{skill.content}

Please follow the above instructions carefully."""

        # Inherit allowed_tools from main agent, excluding use_skill to prevent recursion
        skill_allowed_tools = None
        if allowed_tools is not None:
            skill_allowed_tools = [t for t in allowed_tools if t != "use_skill"]

        config = AgentConfig(
            llm_client=self.llm_client,
            max_iterations=20,
            enable_memory=False,
            role="skill",
            system_prompt=skill_system_prompt,
            pty_manager=pty_manager,
            tools=get_toolset_for_role(
                "skill",
                llm_client=self.llm_client,
                skill_manager=self.skill_manager
            ),
            allowed_tools=skill_allowed_tools,
        )
        return self._create_agent(config, instance_id=f"skill_{skill.name}")

    def create_sub_agent(
        self,
        parent_agent: Agent,
        task_id: Optional[str] = None,
        task_description: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Agent:
        """
        Create sub agent for async task delegation.

        Sub agents:
        - Have their own message queue and worker thread
        - Have their own independent PTY instance (not shared with parent)
        - Have their own AgentFactory (so skill agents use sub agent's PTY)
        - Report results back to parent agent via AgentReplyHandler
        - Can use skills but cannot create nested sub agents
        - PTY is automatically cleaned up after task completion

        Args:
            parent_agent: The parent Agent to report results to
            task_id: Optional task identifier for tracking
            task_description: Optional description of the task
            system_prompt: Optional custom system prompt

        Returns:
            Configured sub Agent instance
        """
        from infrastructure.terminal.pty_manager import PTYManager
        from infrastructure.logging import get_logger

        logger = get_logger("factory.sub_agent")

        # Create independent PTY for sub agent
        sub_pty = PTYManager()
        sub_pty.start()
        logger.info("Created independent PTY for sub agent", task_id=task_id)

        # Create reply handler that forwards to parent and cleans up PTY
        reply_handler = AgentReplyHandler(
            parent_agent=parent_agent,
            task_id=task_id,
            task_description=task_description,
            owned_pty=sub_pty  # Handler will clean up PTY on completion
        )

        # Create independent AgentFactory for sub agent
        # This ensures skill agents created by sub agent use sub agent's PTY
        sub_factory = AgentFactory(
            pty_manager=sub_pty,  # Use sub agent's independent PTY
            skill_manager=self.skill_manager,
            llm_client=self.llm_client
        )

        # Default sub agent prompt
        default_prompt = """# Sub Agent

You are a sub-agent working on a delegated task. Your responsibilities:

1. Complete the assigned task independently
2. Use available tools and skills as needed
3. Report clear, actionable results back to the main agent

## Guidelines

- Focus on the specific task given to you
- Summarize your findings concisely
- If you encounter blockers, report them clearly
- Do not create additional sub-agents

## Reporting

When complete, provide:
- Summary of what was accomplished
- Key findings or results
- Any issues encountered
- Recommendations for next steps (if applicable)
"""

        config = AgentConfig(
            llm_client=self.llm_client,
            max_iterations=20,
            enable_memory=False,
            role="sub",
            system_prompt=system_prompt or default_prompt,
            pty_manager=sub_pty,  # Use independent PTY
            skill_manager=self.skill_manager,  # Sub agent can use skills
            tools=get_toolset_for_role(
                "sub",
                agent_factory=sub_factory,  # Use sub agent's own factory
                skill_manager=self.skill_manager,
                llm_client=self.llm_client
            ),
            response_handler=reply_handler
        )

        instance_id = f"sub_{task_id}" if task_id else f"sub_{id(self)}"

        return self._create_agent(config, instance_id=instance_id)

    def _create_agent(
        self,
        config: AgentConfig,
        instance_id: str
    ) -> Agent:
        """
        Create Agent and register tools.

        Args:
            config: Agent configuration
            agent_id: Unique identifier for the agent

        Returns:
            Configured Agent with all tools registered
        """
        agent = Agent(config)

        # Set instance_id on the agent instance (for worker thread logging)
        agent.set_instance_id(instance_id)

        # Set instance_id in logging context for current thread (creation thread)
        from infrastructure.logging import logger_context
        logger_context.set_agent(agent_id=instance_id)

        # Register TerminalTool (using shared PTY)
        terminal_tool = TerminalTool(
            config.pty_manager,
            instance_id=instance_id
        )
        agent.register_tool(terminal_tool)

        # Register TerminalBufferTool (using shared PTY buffer)
        buffer_tool = TerminalBufferTool(config.pty_manager)
        agent.register_tool(buffer_tool)

        # Register file tools (filtered by allowed_tools in ReactLoop)
        for file_tool in create_file_tools():
            agent.register_tool(file_tool)

        return agent
