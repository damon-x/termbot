"""
Unit tests for toolsets module.

Tests for role-based tool set creation.
"""
import unittest

from agent.tools.toolsets import get_toolset_for_role


class TestSkillToolset(unittest.TestCase):
    """Test skill Agent tool set."""

    def test_skill_toolset(self):
        """Test skill tool set contains expected tools."""
        tools = get_toolset_for_role("skill")
        tool_names = {t.schema.name for t in tools}

        # Check for expected tools
        self.assertIn("add_memory", tool_names)
        self.assertIn("search_memory", tool_names)
        self.assertIn("send_file_user", tool_names)

        # Check that skill-related tools are NOT present
        self.assertNotIn("search_skill", tool_names)
        self.assertNotIn("use_skill", tool_names)
        # Check that disabled tools are NOT present
        self.assertNotIn("send_msg_to_user", tool_names)
        self.assertNotIn("ask_user", tool_names)


class TestMainToolset(unittest.TestCase):
    """Test main Agent tool set."""

    def test_main_toolset(self):
        """Test main Agent tool set contains skill tools."""
        tools = get_toolset_for_role("main")
        tool_names = {t.schema.name for t in tools}

        # Main Agent should at least include memory tools
        self.assertIn("add_memory", tool_names)
        self.assertIn("search_memory", tool_names)
        self.assertIn("send_file_user", tool_names)
        # Main Agent should have use_skill
        self.assertIn("use_skill", tool_names)
        # Check that disabled tools are NOT present
        self.assertNotIn("send_msg_to_user", tool_names)
        self.assertNotIn("ask_user", tool_names)


class TestUnknownRole(unittest.TestCase):
    """Test unknown role returns empty list."""

    def test_unknown_role(self):
        """Test unknown role returns empty tool set."""
        tools = get_toolset_for_role("unknown")
        self.assertEqual(tools, [])
