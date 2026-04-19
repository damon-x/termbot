"""
Unit tests for Agent core components.

Tests the Context, ReactLoop, ToolRegistry, and Agent classes
to ensure they work correctly without external dependencies.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch

from agent.context import Context, Message
from agent.core import Agent, AgentConfig
from agent.react import ReactLoop, ReactStep, ReactResult
from agent.tools.base import (
    Tool,
    ToolSchema,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
    SimpleTool,
)
from agent.tools.impl import WeatherTool, SendMessageTool


class TestContext(unittest.TestCase):
    """Test cases for Context class."""

    def setUp(self):
        """Set up test fixtures."""
        self.context = Context()

    def test_context_initialization(self):
        """Test context initializes with correct defaults."""
        self.assertEqual(self.context.get_status(), "running")
        self.assertEqual(self.context.get_chat_status(), "running")
        self.assertEqual(self.context.message_count, 0)
        self.assertFalse(self.context.is_waiting_user_answer())

    def test_add_message(self):
        """Test adding messages to context."""
        self.context.add_message("user", "Hello")
        self.context.add_message("assistant", "Hi there")

        messages = self.context.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Hello")

    def test_get_messages(self):
        """Test getting messages in LLM format."""
        self.context.add_message("user", "Test message")
        messages = self.context.get_messages()

        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 1)
        self.assertIn("role", messages[0])
        self.assertIn("content", messages[0])

    def test_message_count(self):
        """Test message count property."""
        self.assertEqual(self.context.message_count, 0)
        self.context.add_message("user", "Message 1")
        self.assertEqual(self.context.message_count, 1)
        self.context.add_message("assistant", "Message 2")
        self.assertEqual(self.context.message_count, 2)

    def test_state_management(self):
        """Test state get/set operations."""
        self.context.set_state("key1", "value1")
        self.assertEqual(self.context.get_state("key1"), "value1")
        self.assertIsNone(self.context.get_state("nonexistent"))
        self.assertEqual(self.context.get_state("nonexistent", "default"), "default")

    def test_clear_messages(self):
        """Test clearing all messages."""
        self.context.add_message("user", "Test")
        self.context.add_message("assistant", "Response")
        self.assertEqual(self.context.message_count, 2)

        self.context.clear_messages()
        self.assertEqual(self.context.message_count, 0)

    def test_status_management(self):
        """Test status changes."""
        self.assertTrue(self.context.is_running())

        self.context.set_status("success")
        self.assertTrue(self.context.is_complete())

        self.context.set_status("failed")
        self.assertTrue(self.context.is_failed())

    def test_chat_status(self):
        """Test chat status management."""
        self.context.start_chat()
        self.assertTrue(self.context.is_chat_running())

        self.context.pause_chat("Test reason")
        self.assertTrue(self.context.is_paused())
        self.assertEqual(self.context.get_state("pause_reason"), "Test reason")

    def test_user_answer_management(self):
        """Test user answer handling."""
        self.context.set_waiting_user_answer(True)
        self.assertTrue(self.context.is_waiting_user_answer())

        # set_user_answer only stores the answer; the flag is cleared
        # separately by the ReactLoop (set_waiting_user_answer(False))
        self.context.set_user_answer("My answer")
        self.assertTrue(self.context.is_waiting_user_answer())

        self.context.set_waiting_user_answer(False)
        self.assertFalse(self.context.is_waiting_user_answer())
        self.assertEqual(self.context.get_user_answer(), "My answer")

    def test_checkpoint_export_load(self):
        """Test checkpoint export and load."""
        self.context.add_message("user", "Test message")
        self.context.set_state("test_key", "test_value")

        checkpoint = self.context.export_checkpoint()
        self.assertIn("messages", checkpoint)
        self.assertIn("state", checkpoint)
        self.assertEqual(len(checkpoint["messages"]), 1)

        # Create new context and load checkpoint
        new_context = Context()
        new_context.load_checkpoint(checkpoint)
        self.assertEqual(new_context.message_count, 1)
        self.assertEqual(new_context.get_state("test_key"), "test_value")

    def test_reset(self):
        """Test context reset."""
        self.context.add_message("user", "Test")
        self.context.set_state("key", "value")
        self.context.set_waiting_user_answer(True)

        self.context.reset()
        self.assertEqual(self.context.message_count, 0)
        self.assertIsNone(self.context.get_state("key"))
        self.assertFalse(self.context.is_waiting_user_answer())


class TestToolSchema(unittest.TestCase):
    """Test cases for ToolSchema class."""

    def test_tool_schema_to_dict(self):
        """Test converting schema to OpenAI Function format."""
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="param1",
                    type=ToolParameterType.STRING,
                    description="First parameter",
                    required=True
                ),
                ToolParameter(
                    name="param2",
                    type=ToolParameterType.INTEGER,
                    description="Second parameter",
                    required=False,
                    default=42
                )
            ]
        )

        result = schema.to_dict()

        self.assertEqual(result["type"], "function")
        self.assertEqual(result["function"]["name"], "test_tool")
        self.assertEqual(result["function"]["description"], "A test tool")
        self.assertIn("param1", result["function"]["parameters"]["properties"])
        self.assertIn("param2", result["function"]["parameters"]["properties"])
        self.assertEqual(result["function"]["parameters"]["required"], ["param1"])

    def test_tool_parameter_to_dict(self):
        """Test ToolParameter conversion."""
        param = ToolParameter(
            name="test_param",
            type=ToolParameterType.BOOLEAN,
            description="A boolean parameter",
            required=True
        )

        result = param.to_dict()

        self.assertEqual(result["type"], "boolean")
        self.assertEqual(result["description"], "A boolean parameter")

    def test_tool_schema_with_enum(self):
        """Test tool schema with enum parameter."""
        param = ToolParameter(
            name="choice",
            type=ToolParameterType.STRING,
            description="Make a choice",
            required=True,
            enum=["option1", "option2", "option3"]
        )

        result = param.to_dict()

        self.assertIn("enum", result)
        self.assertEqual(result["enum"], ["option1", "option2", "option3"])


class TestToolRegistry(unittest.TestCase):
    """Test cases for ToolRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = ToolRegistry()

    def test_register_tool(self):
        """Test registering a tool."""
        tool = WeatherTool()
        self.registry.register(tool)

        self.assertTrue(self.registry.has_tool("search_weather"))
        self.assertEqual(self.registry.get_tool_count(), 1)

    def test_register_duplicate_tool(self):
        """Test that duplicate tool names raise error."""
        tool1 = WeatherTool()
        tool2 = WeatherTool()

        self.registry.register(tool1)
        with self.assertRaises(ValueError):
            self.registry.register(tool2)

    def test_get_tool(self):
        """Test retrieving a tool."""
        tool = WeatherTool()
        self.registry.register(tool)

        retrieved = self.registry.get("search_weather")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.schema.name, "search_weather")

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        retrieved = self.registry.get("nonexistent_tool")
        self.assertIsNone(retrieved)

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        tool = WeatherTool()
        self.registry.register(tool)

        self.assertTrue(self.registry.unregister("search_weather"))
        self.assertFalse(self.registry.has_tool("search_weather"))

    def test_list_tools(self):
        """Test listing all tool names."""
        self.registry.register(WeatherTool())
        self.registry.register(SendMessageTool())

        tool_names = self.registry.list_tools()
        self.assertIn("search_weather", tool_names)
        self.assertIn("send_msg_to_user", tool_names)

    def test_get_tool_schemas(self):
        """Test getting all tool schemas."""
        self.registry.register(WeatherTool())
        self.registry.register(SendMessageTool())

        schemas = self.registry.get_tool_schemas()
        self.assertEqual(len(schemas), 2)
        self.assertEqual(schemas[0]["type"], "function")

    def test_execute_tool(self):
        """Test executing a tool through registry."""
        self.registry.register(WeatherTool())

        result = self.registry.execute_tool(
            "search_weather",
            location="Beijing",
            date="2024-01-01"
        )

        self.assertIn("Beijing", result)
        self.assertIn("2024-01-01", result)

    def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        with self.assertRaises(ValueError):
            self.registry.execute_tool("nonexistent", param="value")


class TestSimpleTool(unittest.TestCase):
    """Test cases for SimpleTool class."""

    def test_simple_tool_creation(self):
        """Test creating a simple tool."""
        def test_func(param1: str, param2: int = 10) -> str:
            return f"{param1}: {param2}"

        tool = SimpleTool(
            name="test_tool",
            description="A test tool",
            func=test_func
        )

        self.assertEqual(tool.schema.name, "test_tool")
        result = tool.execute(param1="value", param2=20)
        self.assertEqual(result, "value: 20")


class TestReactLoop(unittest.TestCase):
    """Test cases for ReactLoop class."""

    def setUp(self):
        """Set up test fixtures."""
        self.context = Context()
        self.mock_llm = Mock()

    def test_react_loop_initialization(self):
        """Test ReactLoop initialization."""
        loop = ReactLoop(
            llm_client=self.mock_llm,
            context=self.context,
            max_iterations=10
        )

        self.assertEqual(loop.max_iterations, 10)
        self.assertEqual(loop.get_available_tools(), [])

    def test_register_tool(self):
        """Test registering tools in ReactLoop."""
        loop = ReactLoop(
            llm_client=self.mock_llm,
            context=self.context
        )

        tool = WeatherTool()
        loop.register_tool(tool)

        self.assertIn("search_weather", loop.get_available_tools())

    def test_react_step_to_dict(self):
        """Test ReactStep conversion to dict."""
        step = ReactStep(
            thought="I should check the weather",
            action="search_weather",
            action_input={"location": "Beijing", "date": "2024-01-01"},
            observation="Cloudy"
        )

        result = step.to_dict()

        self.assertEqual(result["thought"], "I should check the weather")
        self.assertEqual(result["action"], "search_weather")
        self.assertEqual(result["observation"], "Cloudy")


class TestAgent(unittest.TestCase):
    """Test cases for Agent class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.config = AgentConfig(
            llm_client=self.mock_llm,
            max_iterations=10,
            enable_memory=False,
            enable_mcp=False
        )

    def test_agent_initialization(self):
        """Test Agent initialization."""
        agent = Agent(self.config)

        self.assertIsNotNone(agent.get_context())
        self.assertEqual(agent.get_status(), "running")
        self.assertEqual(agent.get_message_count(), 0)

    def test_register_tool(self):
        """Test registering tools with Agent."""
        agent = Agent(self.config)

        tool = WeatherTool()
        agent.register_tool(tool)

        tools = agent.get_available_tools()
        self.assertIn("search_weather", tools)

    def test_get_conversation_history(self):
        """Test getting conversation history."""
        agent = Agent(self.config)

        history = agent.get_conversation_history()
        self.assertIsInstance(history, list)

    def test_reset_conversation(self):
        """Test resetting conversation."""
        agent = Agent(self.config)

        # Add some state
        agent.get_context().add_message("user", "Test")

        agent.reset_conversation()
        self.assertEqual(agent.get_message_count(), 0)

    def test_get_tool_schemas(self):
        """Test getting tool schemas."""
        agent = Agent(self.config)
        agent.register_tool(WeatherTool())

        schemas = agent.get_tool_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["function"]["name"], "search_weather")

    def test_checkpoint_export_load(self):
        """Test checkpoint export and load."""
        agent = Agent(self.config)

        agent.get_context().add_message("user", "Test message")
        checkpoint = agent.export_checkpoint()

        self.assertIn("messages", checkpoint)

        # Load into new agent
        new_agent = Agent(self.config)
        new_agent.load_checkpoint(checkpoint)
        self.assertEqual(new_agent.get_message_count(), 1)


class TestMessageDataclass(unittest.TestCase):
    """Test cases for Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(
            role="user",
            content="Hello",
            metadata={"source": "test"}
        )

        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello")
        self.assertEqual(msg.metadata["source"], "test")


class TestToolImplementations(unittest.TestCase):
    """Test cases for tool implementations."""

    def test_weather_tool_schema(self):
        """Test WeatherTool schema."""
        tool = WeatherTool()
        schema = tool.schema

        self.assertEqual(schema.name, "search_weather")
        self.assertGreater(len(schema.parameters), 0)

    def test_weather_tool_execute(self):
        """Test WeatherTool execution."""
        tool = WeatherTool()
        result = tool.execute(location="Beijing", date="2024-01-01")

        self.assertIn("Beijing", result)
        self.assertIn("2024-01-01", result)

    def test_send_message_tool(self):
        """Test SendMessageTool."""
        tool = SendMessageTool()

        # Test without waiting for response
        result = tool.execute(msg="Hello", wait_for_res="N")
        self.assertIn("Hello", result)

    def test_tool_validation(self):
        """Test tool argument validation."""
        tool = WeatherTool()

        # Should raise error for missing required params
        with self.assertRaises(ValueError):
            tool.validate_args({"location": "Beijing"})  # missing date

        # Should pass with all required params
        self.assertTrue(tool.validate_args({
            "location": "Beijing",
            "date": "2024-01-01"
        }))


if __name__ == "__main__":
    unittest.main()
