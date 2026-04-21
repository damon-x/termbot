"""
MCP tool adapter.

Adapts MCP tools to work with the built-in Tool interface.
"""
import json
from typing import Any, Dict

from agent.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from infrastructure.mcp.models import MCPToolInfo
from infrastructure.logging import get_logger

logger = get_logger("tools.mcp_adapter")


class MCPAdapterTool(Tool):
    """
    Adapter that makes MCP tools compatible with the built-in Tool interface.

    This allows MCP tools to be registered and used alongside
    built-in tools in the ReAct loop.
    """

    def __init__(
        self,
        tool_info: MCPToolInfo,
        mcp_manager: 'MCPManager'
    ):
        """
        Initialize MCP adapter tool.

        Args:
            tool_info: MCP tool information
            mcp_manager: MCP manager for executing tool calls
        """
        self._tool_info = tool_info
        self._mcp_manager = mcp_manager
        self._schema = self._convert_schema(tool_info)

    @property
    def schema(self) -> ToolSchema:
        """Get the tool schema."""
        return self._schema

    def _convert_schema(self, tool_info: MCPToolInfo) -> ToolSchema:
        """
        Convert MCP tool schema to built-in ToolSchema.

        Args:
            tool_info: MCP tool information

        Returns:
            ToolSchema instance
        """
        parameters = []

        # Extract properties from JSON schema
        input_schema = tool_info.input_schema
        properties = input_schema.get("properties", {})
        required_fields = input_schema.get("required", [])

        for param_name, param_def in properties.items():
            # Map JSON Schema types to ToolParameterType
            param_type = self._map_json_type(param_def.get("type", "string"))

            parameter = ToolParameter(
                name=param_name,
                type=param_type,
                description=param_def.get("description", ""),
                required=param_name in required_fields,
                default=param_def.get("default"),
                enum=param_def.get("enum")
            )
            parameters.append(parameter)

        # Create tool name with server prefix to avoid conflicts
        prefixed_name = f"{tool_info.server_name}__{tool_info.name}"

        return ToolSchema(
            name=prefixed_name,
            description=f"[MCP:{tool_info.server_name}] {tool_info.description}",
            parameters=parameters
        )

    def _map_json_type(self, json_type: str) -> ToolParameterType:
        """
        Map JSON Schema type to ToolParameterType.

        Args:
            json_type: JSON Schema type string

        Returns:
            ToolParameterType enum value
        """
        type_mapping = {
            "string": ToolParameterType.STRING,
            "integer": ToolParameterType.INTEGER,
            "number": ToolParameterType.NUMBER,
            "boolean": ToolParameterType.BOOLEAN,
            "array": ToolParameterType.ARRAY,
            "object": ToolParameterType.OBJECT
        }

        return type_mapping.get(
            json_type.lower(),
            ToolParameterType.STRING
        )

    def execute(self, **kwargs: Any) -> Any:
        """
        Execute the MCP tool.

        Args:
            **kwargs: Tool arguments

        Returns:
            Tool execution result formatted as string
        """
        try:
            # Always run in the MCP manager's persistent event loop so that
            # subprocess StreamReader/StreamWriter objects are used in the same
            # loop that created them (avoids "Future attached to a different loop").
            return self._mcp_manager.run_async(self._execute_async(kwargs), timeout=60.0)
        except Exception as e:
            logger.error(
                f"MCP tool '{self._tool_info.name}' execution failed: {e}",
                error=str(e)
            )
            return f"Error: {str(e)}"

    async def _execute_async(self, arguments: Dict[str, Any]) -> str:
        """
        Async execution of MCP tool call.

        Args:
            arguments: Tool arguments

        Returns:
            Formatted result string
        """
        try:
            # Call the MCP tool
            result = await self._mcp_manager.call_tool(
                self._tool_info.server_name,
                self._tool_info.name,
                arguments
            )

            # Format result for display
            return self._format_result(result)

        except Exception as e:
            logger.error(
                f"MCP tool call failed: {self._tool_info.server_name}/"
                f"{self._tool_info.name}: {e}"
            )
            raise

    def _format_result(self, result: Any) -> str:
        """
        Format MCP tool result for display.

        Args:
            result: Raw result from MCP tool

        Returns:
            Formatted string result
        """
        # MCP tools can return different result types
        if isinstance(result, str):
            return result

        if hasattr(result, 'content'):
            # Result has content attribute (MCP format)
            content = result.content

            if isinstance(content, list):
                # Multiple content blocks
                formatted_parts = []
                for item in content:
                    if hasattr(item, 'text'):
                        formatted_parts.append(item.text)
                    elif hasattr(item, 'data'):
                        # Binary data (image, etc.)
                        formatted_parts.append(f"[Binary data: {len(item.data)} bytes]")
                    else:
                        formatted_parts.append(str(item))

                return "\n".join(formatted_parts)

            elif isinstance(content, str):
                return content

        # Fallback: JSON encode
        try:
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception:
            return str(result)


class MCPToolFactory:
    """
    Factory for creating MCP adapter tools.

    Scans MCP servers and creates adapter tools for all discovered tools.
    """

    def __init__(self, mcp_manager: 'MCPManager'):
        """
        Initialize MCP tool factory.

        Args:
            mcp_manager: MCP manager instance
        """
        self._mcp_manager = mcp_manager

    async def create_all_tools(self) -> list[Tool]:
        """
        Create adapter tools for all available MCP tools.

        Returns:
            List of MCPAdapterTool instances

        Raises:
            RuntimeError: If MCP manager is not initialized
        """
        # Ensure MCP manager is initialized
        if not self._mcp_manager._is_initialized:
            await self._mcp_manager.initialize()

        tools = []

        # Get all tool info from MCP manager
        all_tool_info = self._mcp_manager.get_all_tools()

        for tool_info in all_tool_info:
            adapter = MCPAdapterTool(tool_info, self._mcp_manager)
            tools.append(adapter)

            logger.debug(
                f"Created MCP adapter tool: {adapter.schema.name} "
                f"(from {tool_info.server_name})"
            )

        logger.info(f"Created {len(tools)} MCP adapter tools")
        return tools

    def create_tool_for_server(
        self,
        server_name: str
    ) -> list[Tool]:
        """
        Create adapter tools for a specific MCP server.

        Args:
            server_name: Name of the MCP server

        Returns:
            List of MCPAdapterTool instances from that server
        """
        tools = []

        tool_infos = self._mcp_manager.get_tools_by_server(server_name)

        for tool_info in tool_infos:
            adapter = MCPAdapterTool(tool_info, self._mcp_manager)
            tools.append(adapter)

        return tools


async def create_mcp_tools(mcp_manager: 'MCPManager') -> list[Tool]:
    """
    Convenience function to create MCP adapter tools.

    Args:
        mcp_manager: MCP manager instance

    Returns:
        List of MCPAdapterTool instances
    """
    factory = MCPToolFactory(mcp_manager)
    return await factory.create_all_tools()
