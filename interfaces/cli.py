"""
CLI interface handler for Agent interaction.

Provides a command-line interface for interacting with the Agent.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.factory import AgentFactory
from interfaces.base import BaseHandler
from infrastructure.logging import logger_context
from infrastructure.storage import create_conversation_logger


class CLIHandler(BaseHandler):
    """
    Command-line interface handler for Agent interaction.

    Provides an interactive CLI session with the agent.
    """

    def __init__(self, agent_factory: AgentFactory, system_prompt: Optional[str] = None) -> None:
        """
        Initialize the CLI handler.

        Args:
            agent_factory: Agent factory for creating agents
            system_prompt: Optional custom system prompt
        """
        # Set logging context for CLI session
        logger_context.set_session(session_id="cli", mode="cli")

        # Create main agent through factory
        agent = agent_factory.create_main_agent(system_prompt)

        # Attach conversation logger
        session_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._conv_logger = create_conversation_logger(session_id=session_id, agent_id="default")
        if self._conv_logger:
            agent.context.set_message_callback(self._conv_logger.log)

        super().__init__(agent)

    def start(self) -> None:
        """Start the CLI interactive session."""
        self._is_running = True
        print("╔══════════════════════════════════════════════════════════╗")
        print("║           TermBot - AI Terminal Assistant                 ║")
        print("║                    Phase 5.4 Demo                          ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        print("Available commands:")
        print("  /help     - Show this help message")
        print("  /tools    - List available tools")
        print("  /mcp      - Show MCP (Model Context Protocol) status")
        print("  /skills   - List available skills")
        print("  /history  - Show conversation history")
        print("  /reset    - Reset conversation")
        print("  /quit     - Exit the session")
        print()
        print("Just type your message and press Enter to chat!")
        print("─" * 60)

    def stop(self) -> None:
        """Stop the CLI session."""
        self._is_running = False
        print()
        print("─" * 60)
        print("Goodbye!")

    def send_message(self, message: str) -> str:
        """
        Send a message to the agent and get response.

        Args:
            message: User's message

        Returns:
            Agent's response
        """
        try:
            result = self.agent.process_message_with_result(message)

            # Handle paused state - ask user for input
            while result.status == "paused":
                # Display the question
                print(f"\n❓ {result.question}")
                if result.options:
                    print(f"选项: {' / '.join(result.options)}")

                # Get user input
                while True:
                    answer = input("\n🧑 Your answer: ").strip()

                    if not answer:
                        continue

                    # Validate options if provided
                    if result.options and answer not in result.options:
                        print(f"⚠️ 请从选项中选择: {result.options}")
                        continue

                    break

                # Provide answer and resume
                self.agent.provide_user_answer(answer)
                result = self.agent.resume_task()

            if result.success:
                return result.response
            return f"Error: {result.error or 'Unknown error'}"
        except Exception as e:
            self._handle_error(e)
            return f"Error: {e}"

    def run_session(self) -> None:
        """Run the interactive CLI session."""
        self.start()

        while self._is_running:
            try:
                # Get user input
                user_input = input("\n🧑 You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # Send message to agent
                print("\n🤖 Agent: ", end="", flush=True)
                response = self.send_message(user_input)
                print(response)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Use /quit to exit.")
            except EOFError:
                break

        self.stop()

    def _handle_command(self, command: str) -> None:
        """
        Handle special commands.

        Args:
            command: Command string starting with /
        """
        cmd = command.lower().strip()

        if cmd == "/help":
            self._show_help()
        elif cmd == "/tools":
            self._show_tools()
        elif cmd == "/mcp":
            self._show_mcp_status()
        elif cmd == "/history":
            self._show_history()
        elif cmd == "/reset":
            self._reset_conversation()
        elif cmd == "/stop":
            self.agent.stop()
            print("\n已发送停止信号。")
        elif cmd in ("/quit", "/exit", "/q"):
            self._is_running = False
        elif cmd.startswith("/skill"):
            # Handle skill commands: /skills, /skill info, /skill reload, /skill disable, /skill enable
            parts = cmd.split(None, 3)
            if len(parts) >= 3 and parts[1] == "skill":
                if parts[2] == "info" and len(parts) >= 4:
                    self._show_skill_info(parts[3])
                elif parts[2] == "reload" and len(parts) >= 4:
                    self._reload_skill(parts[3])
                elif parts[2] == "disable" and len(parts) >= 4:
                    self._disable_skill(parts[3])
                elif parts[2] == "enable" and len(parts) >= 4:
                    self._enable_skill(parts[3])
                else:
                    print("用法: /skill info <name>, /skill reload <name>, /skill disable <name>, 或 /skill enable <name>")
            elif cmd == "/skills":
                self._show_skills()
            else:
                print(f"Unknown command: {command}")
        else:
            print(f"Unknown command: {command}")

    def _show_help(self) -> None:
        """Show help message."""
        print()
        print("Available commands:")
        print("  /help     - Show this help message")
        print("  /tools    - List available tools")
        print("  /mcp      - Show MCP (Model Context Protocol) status")
        print("  /history  - Show conversation history")
        print("  /reset    - Reset conversation")
        print("  /stop     - Stop current agent task")
        print("  /skills   - List available skills")
        print("  /skill info <name>    - Show detailed skill information")
        print("  /skill reload <name>  - Reload a skill from filesystem")
        print("  /skill disable <name> - Disable a skill")
        print("  /skill enable <name>  - Enable a skill")
        print("  /quit     - Exit the session")

    def _show_tools(self) -> None:
        """Show available tools."""
        tools = self.agent.get_available_tools()
        print()
        print(f"Available tools ({len(tools)}):")
        for tool in tools:
            print(f"  • {tool}")

    def _show_mcp_status(self) -> None:
        """Show MCP (Model Context Protocol) status."""
        from infrastructure.mcp import get_mcp_status_text
        from agent.factory import AgentFactory

        print()

        # Try to get MCP manager from agent factory
        # The agent factory might have mcp_manager attribute
        mcp_manager = None

        # Try to access through agent's config
        if hasattr(self.agent, 'config') and hasattr(self.agent.config, 'pty_manager'):
            pty_manager = self.agent.config.pty_manager
            # Try to find the factory that created this agent
            # This is a bit hacky, but we don't have direct access to the factory
            pass

        # Try global MCP manager
        try:
            from infrastructure.mcp import get_mcp_manager
            mcp_manager = get_mcp_manager()
        except Exception:
            pass

        # Display status
        status_text = get_mcp_status_text(mcp_manager)
        print(status_text)

    def _show_history(self) -> None:
        """Show conversation history."""
        history = self.agent.get_conversation_history()
        print()
        print(f"Conversation history ({len(history)} messages):")
        for msg in history[-10:]:  # Show last 10
            role = msg["role"].upper()
            content = msg["content"]
            if len(content) > 100:
                content = content[:97] + "..."
            print(f"  [{role}] {content}")

    def _reset_conversation(self) -> None:
        """Reset the conversation."""
        self.agent.reset_conversation()
        print()
        print("Conversation reset.")

    def _show_steps(self) -> None:
        """Show reasoning steps from last interaction."""
        # This would require storing the last ReactResult
        # TODO: Implement step display when needed

    def _show_skills(self) -> None:
        """Show all available skills."""
        skill_manager = self.agent.config.pty_manager.skill_manager
        basics = skill_manager.list_skill_basics()

        print()
        if not basics:
            print("No skills found in ~/.termbot/skills/")
            print()
            print(f"Available skills ({len(basics)}):")
            for skill in basics:
                print(f"  /{skill['name']:<20} {skill['description']}")
        print()

    def _show_skill_info(self, skill_name: str) -> None:
        """Show detailed information about a skill."""
        skill_manager = self.agent.config.pty_manager.skill_manager
        skill = skill_manager.get_skill_by_name(skill_name)

        print()
        if not skill:
            print(f"Skill '{skill_name}' not found.")
            return

        print(f"Skill: /{skill.name}")
        print(f"Description: {skill.description}")
        print(f"Path: {skill.path}")
        if skill.scripts_dir:
            print(f"Scripts: {skill.scripts_dir}")
        if skill.references_dir:
            print(f"References: {skill.references_dir}")
        if skill.assets_dir:
            print(f"Assets: {skill.assets_dir}")
        print()
        print(f"Content preview:")
        print("─" * 60)
        # Show first few lines of content
        lines = skill.content.split("\n")[:10]
        for line in lines:
            print(f"  {line}")
        print("─" * 60)
        print()

    def _reload_skill(self, skill_name: str) -> None:
        """
        Hot-reload a skill from filesystem.

        Skills are always read from filesystem (no caching), so this
        is mainly a notification that the file has been re-read if needed.
        """
        skill_manager = self.agent.config.pty_manager.skill_manager
        skill = skill_manager.get_skill_by_name(skill_name)

        print()
        if skill:
            print(f"Skill '/{skill_name}' has been reloaded from filesystem.")
            print(f"  Current description: {skill.description}")
        else:
            print(f"Skill '/{skill_name}' not found.")

    def _disable_skill(self, skill_name: str) -> None:
        """Disable a skill by setting enabled=false in SKILL.md frontmatter."""
        import re
        import yaml

        skill_manager = self.agent.config.pty_manager.skill_manager
        skill_path = Path(skill_manager.skills_dir) / skill_name
        skill_md = skill_path / "SKILL.md"

        print()
        if not skill_md.exists():
            print(f"Skill '{skill_name}' not found.")
            return

        try:
            # Read current content
            content = skill_md.read_text(encoding='utf-8')

            # Parse frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                print(f"Invalid SKILL.md format: missing frontmatter.")
                return

            # Parse YAML frontmatter
            frontmatter = yaml.safe_load(match.group(1))
            if not isinstance(frontmatter, dict):
                print(f"Invalid SKILL.md format: frontmatter is not a dict.")
                return

            # Check current status
            current_enabled = frontmatter.get("enabled", True)
            if not current_enabled:
                print(f"Skill '{skill_name}' is already disabled.")
                return

            # Set enabled to false
            frontmatter["enabled"] = False

            # Rebuild file content
            new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)}---\n{content[match.end():]}"
            skill_md.write_text(new_content, encoding='utf-8')

            print(f"✓ Skill '{skill_name}' has been disabled.")
            print(f"  Use '/skill enable {skill_name}' to re-enable it.")
        except Exception as e:
            print(f"Error disabling skill: {e}")

    def _enable_skill(self, skill_name: str) -> None:
        """Enable a skill by setting enabled=true in SKILL.md frontmatter."""
        import re
        import yaml

        skill_manager = self.agent.config.pty_manager.skill_manager
        skill_path = Path(skill_manager.skills_dir) / skill_name
        skill_md = skill_path / "SKILL.md"

        print()
        if not skill_md.exists():
            print(f"Skill '{skill_name}' not found.")
            return

        try:
            # Read current content
            content = skill_md.read_text(encoding='utf-8')

            # Parse frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                print(f"Invalid SKILL.md format: missing frontmatter.")
                return

            # Parse YAML frontmatter
            frontmatter = yaml.safe_load(match.group(1))
            if not isinstance(frontmatter, dict):
                print(f"Invalid SKILL.md format: frontmatter is not a dict.")
                return

            # Check current status
            current_enabled = frontmatter.get("enabled", True)
            if current_enabled:
                print(f"Skill '{skill_name}' is already enabled.")
                return

            # Set enabled to true
            frontmatter["enabled"] = True

            # Rebuild file content
            new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)}---\n{content[match.end():]}"
            skill_md.write_text(new_content, encoding='utf-8')

            print(f"✓ Skill '{skill_name}' has been enabled.")
            print(f"  Use '/skill disable {skill_name}' to disable it.")
        except Exception as e:
            print(f"Error enabling skill: {e}")
