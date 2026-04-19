"""
Integration tests for CLI mode.
"""
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestCLIIntegration:
    """CLI integration tests."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = Mock()
        # Mock chat_with_tools to return simple response
        response = Mock()
        response.content = "Test response"
        response.function_call = None
        client.chat_with_tools = Mock(return_value=response)
        return client

    @pytest.fixture
    def agent(self, mock_llm_client):
        """Create test agent."""
        from agent.core import Agent, AgentConfig
        config = AgentConfig(
            llm_client=mock_llm_client,
            max_iterations=5,
            enable_memory=False,
            enable_mcp=False
        )
        return Agent(config)

    @pytest.fixture
    def cli_handler(self, agent):
        """Create CLI handler."""
        from interfaces.cli import CLIHandler
        return CLIHandler(agent)

    def test_cli_handler_creation(self, cli_handler):
        """Test CLI handler can be created."""
        assert cli_handler is not None
        assert cli_handler.agent is not None

    def test_cli_start(self, cli_handler, capsys):
        """Test CLI start method."""
        cli_handler.start()
        captured = capsys.readouterr()

        assert "TermBot" in captured.out
        assert cli_handler.is_running()

    def test_cli_stop(self, cli_handler, capsys):
        """Test CLI stop method."""
        cli_handler.start()
        cli_handler.stop()
        captured = capsys.readouterr()

        assert "Goodbye" in captured.out
        assert not cli_handler.is_running()

    def test_cli_send_message(self, cli_handler):
        """Test sending message through CLI."""
        response = cli_handler.send_message("Hello")

        assert response is not None
        assert isinstance(response, str)

    def test_cli_command_help(self, cli_handler, capsys):
        """Test /help command."""
        cli_handler._handle_command("/help")
        captured = capsys.readouterr()

        assert "Available commands" in captured.out

    def test_cli_command_tools(self, cli_handler, capsys):
        """Test /tools command."""
        cli_handler._handle_command("/tools")
        captured = capsys.readouterr()

        assert "Available tools" in captured.out

    def test_cli_command_history(self, cli_handler, capsys):
        """Test /history command."""
        cli_handler._handle_command("/history")
        captured = capsys.readouterr()

        assert "Conversation" in captured.out

    def test_cli_command_reset(self, cli_handler, capsys):
        """Test /reset command."""
        cli_handler._handle_command("/reset")
        captured = capsys.readouterr()

        assert "reset" in captured.out.lower()

    def test_cli_unknown_command(self, cli_handler, capsys):
        """Test unknown command."""
        cli_handler._handle_command("/unknown")
        captured = capsys.readouterr()

        assert "Unknown command" in captured.out

    def test_cli_integration_with_agent(self, agent):
        """Test CLI works with agent."""
        from interfaces.cli import CLIHandler

        cli = CLIHandler(agent)

        # Agent should be accessible
        assert cli.agent == agent

        # Tools should be available
        tools = cli.get_available_tools()
        assert isinstance(tools, list)

    def test_cli_conversation_history(self, cli_handler):
        """Test conversation history access."""
        history = cli_handler.get_conversation_history()

        assert isinstance(history, list)

    def test_cli_reset_conversation(self, cli_handler):
        """Test resetting conversation."""
        # Add a message first
        cli_handler.agent.process_message("test")

        # Reset
        cli_handler.reset_conversation()

        # History should be cleared
        history = cli_handler.get_conversation_history()
        # Note: Depending on implementation, system prompt might remain
        assert len(history) <= 1  # Only system prompt if present
