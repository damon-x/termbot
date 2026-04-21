"""
MCP (Model Context Protocol) integration module.

Provides integration with MCP servers for dynamic tool discovery
and execution.
"""
from .models import MCPServerConfig, MCPConfig, MCPToolInfo
from .config import MCPConfigLoader, load_mcp_config
from .manager import MCPManager, MCPServerConnection, get_mcp_manager
from .status import (
    get_mcp_status_text,
    get_mcp_status_detailed,
    get_mcp_tools_summary,
    start_mcp_server_sync,
    stop_mcp_server_sync
)

__all__ = [
    # Models
    'MCPServerConfig',
    'MCPConfig',
    'MCPToolInfo',

    # Configuration
    'MCPConfigLoader',
    'load_mcp_config',

    # Manager
    'MCPManager',
    'MCPServerConnection',
    'get_mcp_manager',

    # Status
    'get_mcp_status_text',
    'get_mcp_status_detailed',
    'get_mcp_tools_summary',
    'start_mcp_server_sync',
    'stop_mcp_server_sync',
]
