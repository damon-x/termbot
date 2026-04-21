"""
MCP server configuration models.

Defines data structures for MCP server configuration and management.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPServerConfig:
    """
    Configuration for a single MCP server.

    Attributes:
        name: Server identifier (unique key)
        description: Human-readable description
        command: Command to start the server (e.g., "npx", "python")
        args: Arguments to pass to the command
        env: Environment variables for the server process
        enabled: Whether this server is enabled
        auto_start: Whether to start this server automatically on initialization
        timeout: Connection timeout in seconds
    """
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    description: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    auto_start: bool = False
    timeout: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "description": self.description,
            "env": self.env,
            "enabled": self.enabled,
            "auto_start": self.auto_start,
            "timeout": self.timeout
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'MCPServerConfig':
        """Create instance from dictionary (loaded from config file)."""
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            description=data.get("description"),
            env=data.get("env", {}),
            enabled=data.get("enabled", True),
            auto_start=data.get("auto_start", False),
            timeout=data.get("timeout", 10)
        )


@dataclass
class MCPConfig:
    """
    Top-level MCP configuration.

    Attributes:
        enabled: Whether MCP functionality is globally enabled
        servers: Dictionary of server configurations keyed by name
    """
    enabled: bool = True
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "enabled": self.enabled,
            "servers": {
                name: server.to_dict()
                for name, server in self.servers.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPConfig':
        """Create instance from dictionary (loaded from config file)."""
        servers = {}
        if "servers" in data:
            for name, server_data in data["servers"].items():
                servers[name] = MCPServerConfig.from_dict(name, server_data)

        return cls(
            enabled=data.get("enabled", True),
            servers=servers
        )

    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """Get list of enabled server configurations."""
        return [
            server for server in self.servers.values()
            if server.enabled
        ]

    def get_auto_start_servers(self) -> List[MCPServerConfig]:
        """Get list of servers configured for auto-start."""
        return [
            server for server in self.servers.values()
            if server.enabled and server.auto_start
        ]


@dataclass
class MCPToolInfo:
    """
    Information about an MCP tool.

    Attributes:
        server_name: Name of the MCP server providing this tool
        name: Tool name
        description: Tool description
        input_schema: JSON Schema for tool input
    """
    server_name: str
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_name": self.server_name,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
