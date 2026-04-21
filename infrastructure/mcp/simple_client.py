"""
Simplified MCP client implementation.

Uses direct subprocess communication instead of stdio_client
to avoid the complexity and issues with the MCP SDK's stdio client.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger

logger = get_logger("mcp.simple_client")


class SimpleMCPServer:
    """
    Simplified MCP server connection.

    Directly manages subprocess and JSON-RPC communication
    without using the complex stdio_client.
    """

    def __init__(self, config):
        """
        Initialize MCP server connection.

        Args:
            config: MCPServerConfig instance
        """
        self.config = config
        self.process: Optional[Any] = None
        self._request_id = 0
        self._tools: List[Dict] = []
        # Serializes concurrent _send_request() calls.
        # MCP over stdio is inherently one-request-at-a-time: the server reads
        # one JSON-RPC line, writes one response line. Without this lock,
        # concurrent callers interleave writes and steal each other's responses.
        self._request_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        if self.process is None:
            return False
        # Process is running if returncode is None (still executing)
        return self.process.returncode is None

    async def start(self) -> bool:
        """
        Start the MCP server process.

        Returns:
            True if started successfully
        """
        # Check if already started
        if self.process is not None:
            logger.warning(f"MCP server '{self.config.name}' is already running")
            return True

        try:
            logger.info(f"Starting MCP server: {self.config.name}")

            # Build environment variables
            import os
            env = os.environ.copy()
            env.update(self.config.env)

            # Expand environment variables in values
            env = {k: os.path.expandvars(v) for k, v in env.items()}

            # Start server process
            self.process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Give server time to start
            await asyncio.sleep(1.0)

            # Check if process started successfully
            if self.process.returncode is not None:
                raise RuntimeError(f"Server process exited with code {self.process.returncode}")

            # Initialize session
            await self._initialize()

            # Discover tools
            await self._discover_tools()

            logger.info(
                f"MCP server '{self.config.name}' started successfully "
                f"with {len(self._tools)} tools"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start MCP server '{self.config.name}': {e}")
            await self.stop()
            return False

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a JSON-RPC request to the server and wait for its response.

        The lock ensures only one request is in-flight at a time, preventing
        concurrent callers from interleaving writes or stealing responses.

        Args:
            request: JSON-RPC request dictionary

        Returns:
            JSON-RPC response dictionary
        """
        if not self.is_running:
            raise RuntimeError("Server is not running")

        async with self._request_lock:
            # Add request ID
            self._request_id += 1
            request["id"] = self._request_id

            # Send request
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()

            # Read response
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=30.0
            )

            if not response_line:
                raise RuntimeError("No response from server")

            response = json.loads(response_line.decode())

            if "error" in response:
                raise RuntimeError(f"MCP error: {response['error']}")

            return response

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a JSON-RPC notification (no id, no response expected).

        Args:
            method: Notification method name
            params: Optional notification parameters
        """
        if not self.is_running:
            raise RuntimeError("Server is not running")

        notification: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params

        notification_json = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_json.encode())
        await self.process.stdin.drain()

    async def _initialize(self) -> None:
        """Initialize the MCP session."""
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "termbot",
                    "version": "1.0.0"
                }
            }
        }

        response = await self._send_request(init_request)

        if "result" not in response:
            raise RuntimeError(f"Initialize failed: {response}")

        logger.info(f"Initialized: {response['result'].get('serverInfo', {}).get('name', 'unknown')}")

        # MCP protocol requires sending initialized notification after initialize response
        await self._send_notification("notifications/initialized")

    async def _discover_tools(self) -> None:
        """Discover available tools from the server."""
        tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list"
        }

        response = await self._send_request(tools_request)

        if "result" not in response or "tools" not in response["result"]:
            raise RuntimeError(f"Failed to list tools: {response}")

        self._tools = response["result"]["tools"]

        for tool in self._tools:
            logger.debug(f"Discovered tool '{tool['name']}' from server '{self.config.name}'")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on this MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        call_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = await self._send_request(call_request)

        if "result" not in response:
            raise RuntimeError(f"Tool call failed: {response}")

        return response["result"]

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of discovered tools."""
        return self._tools.copy()

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if not self.is_running:
            return

        logger.info(f"Stopping MCP server: {self.config.name}")

        try:
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
                except Exception:
                    pass
                self.process = None

        except Exception as e:
            logger.error(f"Error stopping MCP server '{self.config.name}': {e}")

        finally:
            self._tools = []
