"""
Unit tests for AgentFactory.

Tests for creating main and skill agents.
"""
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from agent.factory import AgentFactory
from agent.skills.skill import Skill


class TestCreateMainAgent(unittest.TestCase):
    """Test creating main agent."""

    def test_create_main_agent(self):
        """Test main agent creation."""
        # Create mocks
        mock_pty = Mock()
        mock_skill_manager = Mock()
        mock_llm = Mock()

        factory = AgentFactory(mock_pty, mock_skill_manager, mock_llm)

        # Create main agent
        agent = factory.create_main_agent()

        # Verify agent created
        self.assertIsNotNone(agent)
        self.assertEqual(agent.config.role, "main")
        self.assertIs(agent.config.pty_manager, mock_pty)
        self.assertIs(agent.config.llm_client, mock_llm)

        # Verify tools registered (at least TerminalTool)
        tools = agent.get_available_tools()
        self.assertGreater(len(tools), 0)
        self.assertIn("exec_terminal_cmd", tools)

    def test_create_main_agent_with_custom_prompt(self):
        """Test main agent with custom system prompt."""
        mock_pty = Mock()
        mock_skill_manager = Mock()
        mock_llm = Mock()

        factory = AgentFactory(mock_pty, mock_skill_manager, mock_llm)

        custom_prompt = "You are a helpful assistant."
        agent = factory.create_main_agent(system_prompt=custom_prompt)

        self.assertEqual(agent.config.system_prompt, custom_prompt)


class TestCreateSkillAgent(unittest.TestCase):
    """Test creating skill agent."""

    def test_create_skill_agent(self):
        """Test skill agent creation."""
        mock_pty = Mock()
        mock_skill_manager = Mock()
        mock_llm = Mock()

        factory = AgentFactory(mock_pty, mock_skill_manager, mock_llm)

        # Create test skill
        skill = Skill(
            name="test-skill",
            description="Test skill for unit testing",
            content="# Test\n\nFollow these instructions.",
            path=Path("/tmp/test-skill")
        )

        # Create skill agent
        agent = factory.create_skill_agent(skill)

        # Verify agent created
        self.assertIsNotNone(agent)
        self.assertEqual(agent.config.role, "skill")
        self.assertIs(agent.config.pty_manager, mock_pty)
        self.assertIs(agent.config.llm_client, mock_llm)
        self.assertFalse(agent.config.enable_memory)

        # Verify system prompt contains skill info
        self.assertIn("test-skill", agent.config.system_prompt)
        self.assertIn("Test skill for unit testing", agent.config.system_prompt)
        self.assertIn("Follow these instructions", agent.config.system_prompt)

        # Verify tools registered
        tools = agent.get_available_tools()
        self.assertGreater(len(tools), 0)
        self.assertIn("exec_terminal_cmd", tools)


class TestAgentFactoryAttributes(unittest.TestCase):
    """Test AgentFactory attributes and methods."""

    def test_factory_initialization(self):
        """Test factory stores dependencies."""
        mock_pty = Mock()
        mock_skill_manager = Mock()
        mock_llm = Mock()

        factory = AgentFactory(mock_pty, mock_skill_manager, mock_llm)

        self.assertIs(factory.pty_manager, mock_pty)
        self.assertIs(factory.skill_manager, mock_skill_manager)
        self.assertIs(factory.llm_client, mock_llm)
