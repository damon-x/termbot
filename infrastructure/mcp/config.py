"""
MCP configuration loader.

Handles loading MCP server configuration from JSON files.
"""
import json
import os
from pathlib import Path
from typing import Optional

from infrastructure.logging import get_logger
from .models import MCPConfig, MCPServerConfig

logger = get_logger("mcp.config")


class MCPConfigLoader:
    """
    Loader for MCP configuration files.

    Configuration search order:
    1. ~/.termbot/mcp/servers.json (user config)
    2. ~/.termbot/mcp/servers.local.json (local override)
    3. config/mcp_servers.json (project defaults)
    """

    # Default configuration directory
    DEFAULT_CONFIG_DIR = "~/.termbot/mcp"
    # User configuration file
    USER_CONFIG_FILE = "servers.json"
    # Local override file
    LOCAL_CONFIG_FILE = "servers.local.json"
    # Project default config
    PROJECT_CONFIG_FILE = "config/mcp_servers.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.

        Args:
            config_path: Optional path to configuration file.
                        If not provided, uses default search order.
        """
        self.config_path = config_path
        self._config_cache: Optional[MCPConfig] = None

    def load(self) -> MCPConfig:
        """
        Load MCP configuration from file.

        Returns:
            MCPConfig instance

        Raises:
            FileNotFoundError: If no configuration file is found
            ValueError: If configuration is invalid
        """
        if self._config_cache is not None:
            return self._config_cache

        # Determine config file to load
        config_file = self._find_config_file()

        if config_file is None:
            config_file = self._create_default_config()
            if config_file is None:
                self._config_cache = MCPConfig(enabled=False)
                return self._config_cache

        logger.info(f"Loading MCP configuration from: {config_file}")

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            config = MCPConfig.from_dict(data)
            self._config_cache = config

            logger.info(
                f"Loaded MCP config: {len(config.servers)} servers, "
                f"{len(config.get_enabled_servers())} enabled"
            )

            return config

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in MCP config file {config_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading MCP config from {config_file}: {e}")

    def _create_default_config(self) -> Optional[str]:
        """
        Create default MCP configuration file at the user config path.

        Called automatically on first startup when no config file exists.
        All servers are disabled by default so nothing runs without explicit opt-in.

        Returns:
            Path to the created file, or None if creation failed
        """
        config_dir = Path(self.DEFAULT_CONFIG_DIR).expanduser()
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "cache").mkdir(exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create MCP config directory: {e}")
            return None

        config_file = config_dir / self.USER_CONFIG_FILE
        default_config = {
            "enabled": True,
            "servers": {
                "filesystem": {
                    "description": "Local filesystem read/write access",
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        str(Path.home())
                    ],
                    "enabled": False,
                    "auto_start": False,
                    "env": {}
                },
                "github": {
                    "description": "GitHub repository integration (requires GITHUB_TOKEN)",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "enabled": False,
                    "auto_start": False,
                    "env": {
                        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
                    }
                }
            }
        }

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"Created default MCP config: {config_file}")
            return str(config_file)
        except OSError as e:
            logger.warning(f"Could not create default MCP config: {e}")
            return None

    def _find_config_file(self) -> Optional[str]:
        """
        Find MCP configuration file using search order.

        Returns:
            Path to configuration file, or None if not found
        """
        # If explicit path provided, use it
        if self.config_path:
            if os.path.exists(self.config_path):
                return self.config_path
            logger.warning(f"Explicit config path not found: {self.config_path}")
            return None

        # Expand user directory
        config_dir = Path(self.DEFAULT_CONFIG_DIR).expanduser()

        # Check local override first (highest priority)
        local_config = config_dir / self.LOCAL_CONFIG_FILE
        if local_config.exists():
            return str(local_config)

        # Check user config
        user_config = config_dir / self.USER_CONFIG_FILE
        if user_config.exists():
            return str(user_config)

        # Check project default config
        project_config = Path(self.PROJECT_CONFIG_FILE)
        if project_config.exists():
            return str(project_config)

        return None

    def save_example_config(self, output_path: Optional[str] = None) -> str:
        """
        Save an example configuration file.

        Args:
            output_path: Optional path to save example config.
                        If not provided, saves to ~/.termbot/mcp/servers.json

        Returns:
            Path where example config was saved
        """
        if output_path is None:
            config_dir = Path(self.DEFAULT_CONFIG_DIR).expanduser()
            config_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(config_dir / self.USER_CONFIG_FILE)

        example_config = {
            "enabled": True,
            "servers": {
                "filesystem": {
                    "description": "Local filesystem access",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", str(Path.home() / "projects")],
                    "enabled": False,
                    "auto_start": False
                },
                "github": {
                    "description": "GitHub repository access",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
                    },
                    "enabled": False,
                    "auto_start": False
                }
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(example_config, f, indent=2)

        logger.info(f"Example MCP config saved to: {output_path}")
        return output_path

    def ensure_config_dir(self) -> str:
        """
        Ensure the MCP configuration directory exists.

        Returns:
            Path to configuration directory
        """
        config_dir = Path(self.DEFAULT_CONFIG_DIR).expanduser()
        config_dir.mkdir(parents=True, exist_ok=True)

        # Also create cache directory
        cache_dir = config_dir / "cache"
        cache_dir.mkdir(exist_ok=True)

        return str(config_dir)


def load_mcp_config(config_path: Optional[str] = None) -> MCPConfig:
    """
    Convenience function to load MCP configuration.

    Args:
        config_path: Optional path to configuration file

    Returns:
        MCPConfig instance
    """
    loader = MCPConfigLoader(config_path)
    return loader.load()
