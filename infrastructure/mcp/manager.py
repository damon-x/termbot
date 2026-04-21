"""
MCP server manager.

Manages MCP server lifecycle, connections, and tool discovery.
"""
import asyncio
import threading
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger
from .config import MCPConfigLoader, load_mcp_config
from .models import MCPServerConfig, MCPToolInfo
from .simple_client import SimpleMCPServer

logger = get_logger("mcp.manager")


class MCPServerConnection:
    """
    Represents a connection to an MCP server.

    Manages the subprocess and client session for a single MCP server.
    """

    def __init__(self, config: MCPServerConfig):
        """
        Initialize MCP server connection.

        Args:
            config: Server configuration
        """
        self.config = config
        self._server: Optional[SimpleMCPServer] = None

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server is not None and self._server.is_running

    @property
    def tools(self) -> List[MCPToolInfo]:
        """Get available tools from this server."""
        if not self._server:
            return []

        server_tools = self._server.get_tools()

        # Convert to MCPToolInfo
        tool_infos = []
        for tool in server_tools:
            tool_info = MCPToolInfo(
                server_name=self.config.name,
                name=tool['name'],
                description=tool.get('description', ''),
                input_schema=tool.get('inputSchema', {})
            )
            tool_infos.append(tool_info)

        return tool_infos

    async def start(self) -> bool:
        """
        Start the MCP server process.

        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.warning(f"MCP server '{self.config.name}' is already running")
            return True

        try:
            logger.info(f"Starting MCP server: {self.config.name}")

            # Create and start simple server
            self._server = SimpleMCPServer(self.config)
            success = await self._server.start()

            if success:
                logger.info(
                    f"MCP server '{self.config.name}' started successfully "
                    f"with {len(self.tools)} tools"
                )
            else:
                self._server = None

            return success

        except Exception as e:
            logger.error(f"Failed to start MCP server '{self.config.name}': {e}")
            await self.stop()
            return False

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if not self.is_running:
            return

        logger.info(f"Stopping MCP server: {self.config.name}")

        try:
            if self._server:
                await self._server.stop()
                self._server = None

        except Exception as e:
            logger.error(f"Error stopping MCP server '{self.config.name}': {e}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on this MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If server is not running
        """
        if not self.is_running or not self._server:
            raise RuntimeError(
                f"Cannot call tool: MCP server '{self.config.name}' is not running"
            )

        return await self._server.call_tool(tool_name, arguments)


class MCPManager:
    """
    Manages multiple MCP server connections.

    Handles lifecycle, tool discovery, and tool execution across
    all configured MCP servers.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        auto_start: bool = True
    ):
        """
        Initialize MCP manager.

        Args:
            config_path: Optional path to MCP configuration file
            auto_start: Whether to auto-start configured servers on initialization
        """
        self.config_path = config_path
        self.auto_start = auto_start

        self._config: Optional[MCPConfig] = None
        self._connections: Dict[str, MCPServerConnection] = {}
        self._is_initialized = False

        # Persistent event loop running in a background daemon thread.
        # All async MCP operations (subprocess I/O, tool calls) must run in
        # this loop so that asyncio StreamReader/StreamWriter objects are never
        # transferred across different loops.
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="mcp-event-loop"
        )
        self._loop_thread.start()

    def run_async(self, coro, timeout: float = 60.0):
        """
        Run a coroutine in the persistent MCP event loop (thread-safe).

        This is the only correct way to call MCP async methods from synchronous
        code. All subprocess I/O is bound to self._loop, so every operation
        must run here to avoid "Future attached to a different loop" errors.

        Args:
            coro: Coroutine to execute
            timeout: Maximum seconds to wait for the result

        Returns:
            Coroutine return value
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    @property
    def is_enabled(self) -> bool:
        """Check if MCP is enabled in configuration."""
        if self._config is None:
            return False
        return self._config.enabled

    @property
    def connections(self) -> Dict[str, MCPServerConnection]:
        """Get all server connections."""
        return self._connections.copy()

    def get_all_tools(self) -> List[MCPToolInfo]:
        """
        Get all available tools from all connected servers.

        Returns:
            List of all available tool information
        """
        all_tools = []
        for connection in self._connections.values():
            if connection.is_running:
                all_tools.extend(connection.tools)
        return all_tools

    def get_tools_by_server(self, server_name: str) -> List[MCPToolInfo]:
        """
        Get tools from a specific server.

        Args:
            server_name: Name of the MCP server

        Returns:
            List of tool information from the server
        """
        connection = self._connections.get(server_name)
        if connection and connection.is_running:
            return connection.tools
        return []

    async def initialize(self) -> None:
        """
        Initialize MCP manager.

        Loads configuration and optionally starts servers.
        """
        if self._is_initialized:
            return

        logger.info("Initializing MCP manager")

        # Load configuration
        loader = MCPConfigLoader(self.config_path)
        self._config = loader.load()

        if not self._config.enabled:
            logger.info("MCP is disabled in configuration")
            self._is_initialized = True
            return

        # Create connection objects for enabled servers
        for server_config in self._config.get_enabled_servers():
            connection = MCPServerConnection(server_config)
            self._connections[server_config.name] = connection

            # Auto-start if configured
            if self.auto_start and server_config.auto_start:
                await connection.start()

        self._is_initialized = True
        logger.info(
            f"MCP manager initialized: {len(self._connections)} servers configured, "
            f"{sum(1 for c in self._connections.values() if c.is_running)} running"
        )

    async def start_server(self, server_name: str) -> bool:
        """
        Start a specific MCP server.

        Args:
            server_name: Name of the server to start

        Returns:
            True if started successfully
        """
        if not self._is_initialized:
            await self.initialize()

        connection = self._connections.get(server_name)
        if not connection:
            logger.error(f"Unknown MCP server: {server_name}")
            return False

        return await connection.start()

    async def stop_server(self, server_name: str) -> None:
        """
        Stop a specific MCP server.

        Args:
            server_name: Name of the server to stop
        """
        connection = self._connections.get(server_name)
        if connection:
            await connection.stop()

    async def start_all_servers(self) -> None:
        """Start all configured MCP servers."""
        if not self._is_initialized:
            await self.initialize()

        for connection in self._connections.values():
            if not connection.is_running:
                await connection.start()

    async def stop_all_servers(self) -> None:
        """Stop all running MCP servers."""
        for connection in self._connections.values():
            await connection.stop()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Call a tool on a specific MCP server.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If server is not running
        """
        connection = self._connections.get(server_name)
        if not connection or not connection.is_running:
            raise RuntimeError(
                f"Cannot call tool: MCP server '{server_name}' is not running"
            )

        return await connection.call_tool(tool_name, arguments)

    async def shutdown(self) -> None:
        """Shutdown MCP manager and stop all servers."""
        logger.info("Shutting down MCP manager")
        await self.stop_all_servers()
        self._connections.clear()
        self._is_initialized = False


# Global singleton instance
_global_mcp_manager: Optional[MCPManager] = None


def get_mcp_manager(
    config_path: Optional[str] = None,
    auto_start: bool = True
) -> MCPManager:
    """
    Get global MCP manager instance.

    Args:
        config_path: Optional path to MCP configuration file
        auto_start: Whether to auto-start configured servers

    Returns:
        MCPManager singleton instance
    """
    global _global_mcp_manager

    if _global_mcp_manager is None:
        _global_mcp_manager = MCPManager(
            config_path=config_path,
            auto_start=auto_start
        )

    return _global_mcp_manager
