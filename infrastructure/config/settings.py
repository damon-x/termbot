"""
Configuration management module.

This module provides a centralized configuration management system
that supports environment variable substitution and hierarchical access.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict


class Settings:
    """
    Configuration management class.

    Supports loading configuration from JSON files with environment
    variable substitution and dot-notation access.
    """

    def __init__(self, env: str = "default") -> None:
        """
        Initialize settings.

        Args:
            env: Environment name (default, development, production)
        """
        self.env = env
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration file.

        Returns:
            Configuration dictionary with environment variables substituted

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            json.JSONDecodeError: If configuration file is invalid JSON
        """
        config_path = Path(f"config/{self.env}.json")
        if not config_path.exists():
            # Fallback to default.json
            config_path = Path("config/default.json")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Replace environment variables
        config = self._replace_env_vars(config)
        return config

    def _replace_env_vars(self, config: Any) -> Any:
        """
        Recursively replace environment variables in configuration.

        Args:
            config: Configuration value (string, dict, or list)

        Returns:
            Configuration with environment variables replaced
        """
        if isinstance(config, str):
            if config.startswith("${") and config.endswith("}"):
                env_var = config[2:-1]
                return os.getenv(env_var)
            return config
        elif isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path.

        Args:
            key: Dot-separated key path (e.g., 'llm.model')
            default: Default value if key not found

        Returns:
            Configuration value or default if not found
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    @property
    def agent(self) -> Dict[str, Any]:
        """Get agent configuration section."""
        result = self._config.get("agent", {})
        return result if isinstance(result, dict) else {}

    @property
    def llm(self) -> Dict[str, Any]:
        """Get LLM configuration section."""
        return self._config.get("llm", {})

    @property
    def terminal(self) -> Dict[str, Any]:
        """Get terminal configuration section."""
        return self._config.get("terminal", {})

    @property
    def memory(self) -> Dict[str, Any]:
        """Get memory configuration section."""
        return self._config.get("memory", {})

    @property
    def mcp(self) -> Dict[str, Any]:
        """Get MCP configuration section."""
        return self._config.get("mcp", {})

    @property
    def logging(self) -> Dict[str, Any]:
        """Get logging configuration section."""
        return self._config.get("logging", {})


# Global settings instance
settings = Settings()
