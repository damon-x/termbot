"""
Tool base module for agent tool abstraction.

Provides base classes and interfaces for implementing tools
that can be used by the agent during ReAct loop execution.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger, EventType

logger = get_logger("tool.base")


class ToolParameterType(Enum):
    """
    Tool parameter types for schema generation.

    Corresponds to JSON Schema types for OpenAI Function Calling.
    """
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """
    Definition of a tool parameter.

    Attributes:
        name: Parameter name
        type: Parameter type
        description: Parameter description for the LLM
        required: Whether the parameter is required
        default: Default value for optional parameters
        enum: Optional list of allowed values
    """
    name: str
    type: ToolParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON Schema format.

        Returns:
            Parameter definition in JSON Schema format
        """
        param_dict: Dict[str, Any] = {
            "type": self.type.value,
            "description": self.description
        }

        if self.default is not None:
            param_dict["default"] = self.default

        if self.enum is not None:
            param_dict["enum"] = self.enum

        return param_dict


@dataclass
class ToolSchema:
    """
    Schema definition for a tool.

    This schema can be converted to OpenAI Function format
    for use with Function Calling.

    Attributes:
        name: Tool name (must be unique)
        description: Tool description for the LLM
        parameters: List of parameter definitions
    """
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to OpenAI Function format.

        Returns:
            Tool schema in OpenAI Function format
        """
        properties: Dict[str, Dict[str, Any]] = {}
        required: List[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_dict()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

    def add_parameter(
        self,
        name: str,
        param_type: ToolParameterType,
        description: str,
        required: bool = True,
        default: Any = None,
        enum: Optional[List[Any]] = None
    ) -> None:
        """
        Add a parameter to the schema.

        Args:
            name: Parameter name
            param_type: Parameter type
            description: Parameter description
            required: Whether the parameter is required
            default: Default value for optional parameters
            enum: Optional list of allowed values
        """
        parameter = ToolParameter(
            name=name,
            type=param_type,
            description=description,
            required=required,
            default=default,
            enum=enum
        )
        self.parameters.append(parameter)


class Tool(ABC):
    """
    Abstract base class for agent tools.

    All tools must inherit from this class and implement
    the schema property and execute method.
    """

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """
        Get the tool schema.

        Returns:
            ToolSchema instance describing the tool
        """
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """
        Execute the tool with given arguments.

        Args:
            **kwargs: Tool arguments as keyword arguments

        Returns:
            Tool execution result (will be converted to string)
        """
        pass

    def validate_args(self, args: Dict[str, Any]) -> bool:
        """
        Validate tool arguments against schema.

        Args:
            args: Arguments to validate

        Returns:
            True if arguments are valid

        Raises:
            ValueError: If arguments are invalid
        """
        required_params = {
            p.name for p in self.schema.parameters if p.required
        }

        # Check for missing required parameters
        missing = required_params - set(args.keys())
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        # Check for extra parameters
        valid_params = {p.name for p in self.schema.parameters}
        extra = set(args.keys()) - valid_params
        if extra:
            raise ValueError(f"Unexpected parameters: {extra}")

        return True


class ToolRegistry:
    """
    Registry for managing available tools.

    Provides registration, retrieval, and schema generation
    for all available tools.
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        tool_name = tool.schema.name
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")
        self._tools[tool_name] = tool

    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool by name.

        Args:
            tool_name: Name of the tool to unregister

        Returns:
            True if tool was unregistered, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            name: Tool name

        Returns:
            True if tool is registered
        """
        return name in self._tools

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get all tool schemas in OpenAI Function format.

        Returns:
            List of tool schema dicts
        """
        return [tool.schema.to_dict() for tool in self._tools.values()]

    def list_tools(self) -> List[str]:
        """
        List all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_tool_count(self) -> int:
        """
        Get the number of registered tools.

        Returns:
            Number of tools
        """
        return len(self._tools)

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()

    def execute_tool(self, name: str, **kwargs: Any) -> Any:
        """
        Execute a tool by name with arguments.

        Args:
            name: Tool name
            **kwargs: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool is not found
        """
        tool = self.get(name)
        if tool is None:
            logger.error(f"Tool not found: {name}")
            raise ValueError(f"Tool '{name}' not found")
        
        import time
        import json
        start_time = time.time()

        try:
            # INFO 级别：简洁的工具调用信息（包含入参）
            # 格式化参数显示（限制长度）
            args_preview = json.dumps(kwargs, ensure_ascii=False)
            if len(args_preview) > 400:
                args_preview = args_preview[:400] + "..."
            logger.info(f"🔧 Tool: {name}({args_preview})")

            result = tool.execute(**kwargs)

            duration_ms = (time.time() - start_time) * 1000
            # DEBUG 级别：详细时间
            logger.debug(f"Tool completed: {name}", duration_ms=round(duration_ms, 2))

            return result

        except Exception as e:
            logger.error(f"Tool failed: {name}", error=str(e))
            raise


class SimpleTool(Tool):
    """
    Simple tool implementation for basic use cases.

    Allows creating tools with just a name, description,
    and a callable function.
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: callable,
        parameters: Optional[List[ToolParameter]] = None
    ) -> None:
        """
        Initialize a simple tool.

        Args:
            name: Tool name
            description: Tool description
            func: Callable that executes the tool
            parameters: Optional list of parameter definitions
        """
        self._schema = ToolSchema(
            name=name,
            description=description,
            parameters=parameters or []
        )
        self._func = func

    @property
    def schema(self) -> ToolSchema:
        """Get the tool schema."""
        return self._schema

    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool function."""
        return self._func(**kwargs)
