"""
Unit tests for skill tools.

Tests for SkillSearchTool and SkillExecutorTool.
"""
import unittest
from unittest.mock import Mock

from agent.tools.skill_search import SkillSearchTool
from agent.tools.skill_executor import SkillExecutorTool


class TestSkillSearchTool(unittest.TestCase):
    """Test cases for SkillSearchTool."""

    def test_skill_search_tool_schema(self):
        """Test skill search tool has correct schema."""
        mock_skill_manager = Mock()
        mock_llm = Mock()

        tool = SkillSearchTool(mock_skill_manager, mock_llm)

        schema = tool.schema
        self.assertEqual(schema.name, "search_skill")
        self.assertIn("需要特定领域的专业知识或工具时", schema.description)
        self.assertEqual(len(schema.parameters), 1)
        self.assertEqual(schema.parameters[0].name, "query")

    def test_skill_search_execute_no_matches(self):
        """Test skill search with no matching skills."""
        mock_skill_manager = Mock()
        mock_llm = Mock()
        mock_skill_manager.search_skill_by_llm.return_value = []
        mock_llm.chat.return_value = Mock(content="")

        tool = SkillSearchTool(mock_skill_manager, mock_llm)
        result = tool.execute(query="PDF 处理")

        self.assertIn("未找到", result)
        self.assertIn("PDF 处理", result)

    def test_skill_search_execute_with_matches(self):
        """Test skill search with matching skills."""
        mock_skill_manager = Mock()
        mock_llm = Mock()

        # Mock search results
        mock_skill_manager.search_skill_by_llm.return_value = [
            {"name": "pdf", "description": "PDF 处理"},
            {"name": "git", "description": "Git 工具"}
        ]
        mock_llm.chat.return_value = Mock(content="pdf, git")

        tool = SkillSearchTool(mock_skill_manager, mock_llm)
        result = tool.execute(query="文档处理")

        self.assertIn("找到 2 个相关 skill", result)
        self.assertIn("/pdf: PDF 处理", result)
        self.assertIn("/git: Git 工具", result)


class TestSkillExecutorTool(unittest.TestCase):
    """Test cases for SkillExecutorTool."""

    def test_skill_executor_tool_schema(self):
        """Test skill executor tool has correct schema."""
        mock_factory = Mock()

        tool = SkillExecutorTool(mock_factory)

        schema = tool.schema
        self.assertEqual(schema.name, "use_skill")
        self.assertIn("使用指定的 skill 执行子任务", schema.description)
        self.assertEqual(len(schema.parameters), 2)
        self.assertEqual(schema.parameters[0].name, "skill_name")
        self.assertEqual(schema.parameters[1].name, "task")

    def test_skill_executor_execute_not_found(self):
        """Test skill executor with non-existent skill."""
        mock_factory = Mock()
        mock_factory.skill_manager.get_skill_by_name.return_value = None

        tool = SkillExecutorTool(mock_factory)
        result = tool.execute(skill_name="nonexistent", task="测试任务")

        self.assertIn("未找到", result)
        self.assertIn("nonexistent", result)

    def test_skill_executor_execute_success(self):
        """Test skill executor with successful execution."""
        from agent.skills.skill import Skill
        from pathlib import Path

        mock_factory = Mock()
        mock_skill = Skill(
            name="test",
            description="Test skill",
            content="Test content",
            path=Path("/tmp/test")
        )
        mock_factory.skill_manager.get_skill_by_name.return_value = mock_skill

        # Mock skill agent
        mock_skill_agent = Mock()
        mock_skill_agent.process_message_with_result.return_value = Mock(
            success=True,
            response="Test result"
        )
        mock_factory.create_skill_agent.return_value = mock_skill_agent

        tool = SkillExecutorTool(mock_factory)
        result = tool.execute(skill_name="test", task="执行测试")

        self.assertEqual(result, "Test result")
        mock_factory.create_skill_agent.assert_called_once_with(mock_skill)

    def test_skill_executor_execute_error(self):
        """Test skill executor with execution error."""
        from agent.skills.skill import Skill
        from pathlib import Path

        mock_factory = Mock()
        mock_skill = Skill(
            name="test",
            description="Test skill",
            content="Test content",
            path=Path("/tmp/test")
        )
        mock_factory.skill_manager.get_skill_by_name.return_value = mock_skill

        # Mock skill agent returning error
        mock_skill_agent = Mock()
        mock_skill_agent.process_message_with_result.return_value = Mock(
            success=False,
            error="Execution failed"
        )
        mock_factory.create_skill_agent.return_value = mock_skill_agent

        tool = SkillExecutorTool(mock_factory)
        result = tool.execute(skill_name="test", task="执行测试")

        self.assertIn("执行失败", result)
        self.assertIn("Execution failed", result)
