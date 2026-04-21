"""
MCP status utility.

Provides functions to query and display MCP server status.
"""
import asyncio
from typing import Dict, List, Optional

from infrastructure.logging import get_logger

logger = get_logger("mcp.status")


def get_mcp_status_text(mcp_manager: 'MCPManager') -> str:
    """
    Get formatted MCP status text for display.

    Args:
        mcp_manager: MCP manager instance

    Returns:
        Formatted status string
    """
    if mcp_manager is None:
        return "❌ MCP 管理器未初始化"

    if not mcp_manager._is_initialized:
        return "⚠️  MCP 管理器未初始化\n   提示: Agent 启动时会自动初始化 MCP"

    if not mcp_manager.is_enabled:
        return "⚠️  MCP 功能已禁用\n   提示: 在 config/default.json 或 ~/.termbot/mcp/servers.json 中启用"

    lines = []
    lines.append("🔌 MCP 状态")
    lines.append("")

    # Get all connections
    connections = mcp_manager.connections

    if not connections:
        lines.append("  未配置任何 MCP 服务器")
        lines.append("")
        lines.append("  配置步骤:")
        lines.append("  1. 运行: .venv/bin/python3 scripts/init_mcp_config.py")
        lines.append("  2. 编辑: ~/.termbot/mcp/servers.json")
        return "\n".join(lines)

    # Count running servers
    running_count = sum(1 for c in connections.values() if c.is_running)
    lines.append(f"  服务器: {len(connections)} 个配置, {running_count} 个运行中")
    lines.append("")

    # List server status
    for server_name, connection in connections.items():
        status_icon = "✅" if connection.is_running else "❌"
        lines.append(f"  {status_icon} {server_name}")

        if connection.is_running:
            # Show tool count
            tool_count = len(connection.tools)
            lines.append(f"     工具: {tool_count} 个可用")

            # Show some tool names (first 3)
            if connection.tools:
                tool_names = [tool.name for tool in connection.tools[:3]]
                if len(connection.tools) > 3:
                    tool_names.append(f"... (+{len(connection.tools) - 3} more)")
                lines.append(f"     示例: {', '.join(tool_names)}")
        else:
            lines.append(f"     状态: 未运行")

        lines.append("")

    # Show all available MCP tools
    all_tools = mcp_manager.get_all_tools()
    if all_tools:
        lines.append(f"  总计: {len(all_tools)} 个 MCP 工具可用")
        lines.append("")
        lines.append("  工具列表:")
        for tool in all_tools[:10]:  # Show first 10
            tool_name = f"{tool.server_name}__{tool.name}"
            lines.append(f"    • {tool_name}")

        if len(all_tools) > 10:
            lines.append(f"    ... 还有 {len(all_tools) - 10} 个工具")
    else:
        lines.append("  总计: 无可用工具")
        lines.append("")
        lines.append("  提示: 启动 MCP 服务器以发现工具")

    return "\n".join(lines)


async def get_mcp_status_detailed(mcp_manager: 'MCPManager') -> Dict:
    """
    Get detailed MCP status as dictionary.

    Args:
        mcp_manager: MCP manager instance

    Returns:
        Dictionary with detailed status information
    """
    if mcp_manager is None:
        return {
            "initialized": False,
            "enabled": False,
            "error": "MCP manager not initialized"
        }

    if not mcp_manager._is_initialized:
        return {
            "initialized": False,
            "enabled": mcp_manager.is_enabled,
            "error": "MCP manager not initialized"
        }

    servers = []
    all_tools = mcp_manager.get_all_tools()

    for server_name, connection in mcp_manager.connections.items():
        server_info = {
            "name": server_name,
            "running": connection.is_running,
            "tool_count": len(connection.tools),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in connection.tools
            ]
        }
        servers.append(server_info)

    return {
        "initialized": True,
        "enabled": mcp_manager.is_enabled,
        "servers": servers,
        "total_tools": len(all_tools)
    }


def get_mcp_tools_summary(mcp_manager: 'MCPManager') -> str:
    """
    Get summary of MCP tools.

    Args:
        mcp_manager: MCP manager instance

    Returns:
        Formatted tools summary
    """
    if mcp_manager is None or not mcp_manager._is_initialized:
        return "MCP 未初始化"

    all_tools = mcp_manager.get_all_tools()

    if not all_tools:
        return "无 MCP 工具可用"

    lines = []
    lines.append(f"📦 MCP 工具 ({len(all_tools)} 个)")
    lines.append("")

    # Group by server
    tools_by_server: Dict[str, List[str]] = {}
    for tool in all_tools:
        if tool.server_name not in tools_by_server:
            tools_by_server[tool.server_name] = []
        tools_by_server[tool.server_name].append(tool.name)

    for server_name, tool_names in sorted(tools_by_server.items()):
        lines.append(f"  {server_name}:")
        for tool_name in sorted(tool_names)[:5]:  # Show first 5 per server
            lines.append(f"    • {tool_name}")
        if len(tool_names) > 5:
            lines.append(f"    ... (+{len(tool_names) - 5} more)")
        lines.append("")

    return "\n".join(lines)


def start_mcp_server_sync(mcp_manager: 'MCPManager', server_name: str) -> str:
    """
    Synchronously start an MCP server.

    Args:
        mcp_manager: MCP manager instance
        server_name: Name of server to start

    Returns:
        Status message
    """
    try:
        success = asyncio.run(mcp_manager.start_server(server_name))
        if success:
            return f"✅ 已启动 MCP 服务器: {server_name}"
        else:
            return f"❌ 启动失败: {server_name}"
    except Exception as e:
        return f"❌ 启动错误: {e}"


def stop_mcp_server_sync(mcp_manager: 'MCPManager', server_name: str) -> str:
    """
    Synchronously stop an MCP server.

    Args:
        mcp_manager: MCP manager instance
        server_name: Name of server to stop

    Returns:
        Status message
    """
    try:
        asyncio.run(mcp_manager.stop_server(server_name))
        return f"✅ 已停止 MCP 服务器: {server_name}"
    except Exception as e:
        return f"❌ 停止错误: {e}"
