#!/usr/bin/env python3
"""
TermBot CLI Mode Entry Point

Standard entry point for running TermBot in CLI mode.
Can be invoked with: python -m termbot.cli
"""
import os
import sys
from pathlib import Path

# 必须在导入其他模块前初始化日志系统，确保第三方库日志被禁用
from infrastructure.logging import init_logging
init_logging(level="INFO")

def load_env_file(env_file: str = ".env") -> None:
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file
    """
    env_path = Path(env_file)
    if not env_path.exists():
        print(f"Warning: {env_file} not found. Using default configuration.")
        return

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE format
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Set environment variable (don't override existing)
                if key not in os.environ:
                    os.environ[key] = value


def main() -> int:
    """Main entry point for CLI mode."""
    # Load .env file
    load_env_file()

    # Check API key
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        print("⚠️  Warning: LLM_API_KEY not set!")
        print()
        print("Please edit .env file and set your API key:")
        print("  LLM_API_KEY=your-api-key-here")
        print()
        return 1

    # Import after loading env vars
    from infrastructure.llm import get_client
    from infrastructure.terminal.pty_manager import PTYManager
    from agent.skills import SkillManager
    from agent.factory import AgentFactory
    from interfaces.cli import CLIHandler

    # Create LLM client (auto-select based on config)
    llm_client = get_client()

    # Initialize PTY Manager
    print("Initializing PTY Manager...")
    pty_manager = PTYManager(
        shell="/bin/bash",
        cols=80,
        rows=24,
        session_timeout=2.0
    )
    pty_manager.start()
    print(f"PTY started (PID: {pty_manager.pid})")

    # Create Skill Manager
    skill_manager = SkillManager()

    # Create Agent Factory
    agent_factory = AgentFactory(pty_manager, skill_manager, llm_client)

    # Create system prompt for main agent
    system_prompt = """You are an intelligent terminal assistant with access to various tools.

## Available Tools

1. exec_terminal_cmd - Execute commands in the terminal
   - Use this to run shell commands, check system status, manage files, etc.
   - Examples: ls, pwd, cat file.txt, docker ps, etc.

2. add_note - Record notes for future reference
   - Use this to remember important information

3. get_all_note - Retrieve all notes
   - Use this when user asks about previously mentioned information

4. send_msg_to_user - Send messages to the user
   - Use this when you need to communicate something important

## Important Guidelines

- When user asks about terminal operations, use exec_terminal_cmd
- When user asks about information mentioned before, check notes first
- Provide clear, helpful responses
- If a command fails, you can try alternative approaches

Use tools when helpful to complete the user's request."""

    # Create CLI Handler (will create main agent through factory)
    cli = CLIHandler(agent_factory, system_prompt)

    try:
        cli.run_session()
    except KeyboardInterrupt:
        print("\n\nSession interrupted.")
    finally:
        # Cleanup PTY
        print("\nStopping PTY...")
        pty_manager.stop()
        print("PTY stopped.")
        print("\nTermBot CLI ended.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
