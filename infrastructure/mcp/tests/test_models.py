"""
Unit tests for MCP models.
"""
import json
import pytest

from infrastructure.mcp.models import MCPServerConfig, MCPConfig, MCPToolInfo


class TestMCPServerConfig:
    """Test MCPServerConfig model."""

    def test_create_config(self):
        """Test creating server configuration."""
        config = MCPServerConfig(
            name="test_server",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-test"],
            description="Test server",
            enabled=True,
            auto_start=False
        )

        assert config.name == "test_server"
        assert config.command == "npx"
        assert config.args == ["-y", "@modelcontextprotocol/server-test"]
        assert config.description == "Test server"
        assert config.enabled is True
        assert config.auto_start is False

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = MCPServerConfig(
            name="test_server",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-test"]
        )

        data = config.to_dict()

        assert data["name"] == "test_server"
        assert data["command"] == "npx"
        assert data["args"] == ["-y", "@modelcontextprotocol/server-test"]

    def test_from_dict(self):
        """Test creating configuration from dictionary."""
        data = {
            "name": "test_server",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-test"],
            "description": "Test server",
            "enabled": True,
            "auto_start": False,
            "timeout": 10
        }

        config = MCPServerConfig.from_dict("test_server", data)

        assert config.name == "test_server"
        assert config.command == "npx"
        assert config.enabled is True


class TestMCPConfig:
    """Test MCPConfig model."""

    def test_create_config(self):
        """Test creating MCP configuration."""
        server_config = MCPServerConfig(
            name="test_server",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-test"]
        )

        config = MCPConfig(
            enabled=True,
            servers={"test_server": server_config}
        )

        assert config.enabled is True
        assert len(config.servers) == 1
        assert "test_server" in config.servers

    def test_get_enabled_servers(self):
        """Test getting enabled servers."""
        server1 = MCPServerConfig(
            name="server1",
            command="npx",
            args=["test1"],
            enabled=True
        )
        server2 = MCPServerConfig(
            name="server2",
            command="npx",
            args=["test2"],
            enabled=False
        )

        config = MCPConfig(
            enabled=True,
            servers={"server1": server1, "server2": server2}
        )

        enabled = config.get_enabled_servers()

        assert len(enabled) == 1
        assert enabled[0].name == "server1"

    def test_get_auto_start_servers(self):
        """Test getting auto-start servers."""
        server1 = MCPServerConfig(
            name="server1",
            command="npx",
            args=["test1"],
            enabled=True,
            auto_start=True
        )
        server2 = MCPServerConfig(
            name="server2",
            command="npx",
            args=["test2"],
            enabled=True,
            auto_start=False
        )

        config = MCPConfig(
            enabled=True,
            servers={"server1": server1, "server2": server2}
        )

        auto_start = config.get_auto_start_servers()

        assert len(auto_start) == 1
        assert auto_start[0].name == "server1"

    def test_from_dict(self):
        """Test creating configuration from dictionary."""
        data = {
            "enabled": True,
            "servers": {
                "test_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-test"],
                    "enabled": True
                }
            }
        }

        config = MCPConfig.from_dict(data)

        assert config.enabled is True
        assert len(config.servers) == 1
        assert "test_server" in config.servers


class TestMCPToolInfo:
    """Test MCPToolInfo model."""

    def test_create_tool_info(self):
        """Test creating tool information."""
        tool_info = MCPToolInfo(
            server_name="test_server",
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object", "properties": {}}
        )

        assert tool_info.server_name == "test_server"
        assert tool_info.name == "test_tool"
        assert tool_info.description == "Test tool"
        assert tool_info.input_schema == {"type": "object", "properties": {}}

    def test_to_dict(self):
        """Test converting tool info to dictionary."""
        tool_info = MCPToolInfo(
            server_name="test_server",
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"}
        )

        data = tool_info.to_dict()

        assert data["server_name"] == "test_server"
        assert data["name"] == "test_tool"
        assert data["description"] == "Test tool"
